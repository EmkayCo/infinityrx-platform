import { AuthError } from "./errors.js";

/**
 * Per SD-1 §11 portal adoption: concurrent invocations of the jwt() callback
 * (or any client-side refresh trigger) keyed by the SAME refresh jti must
 * coalesce to ONE network call. Without coalescing, two simultaneous attempts
 * to refresh the same token race the SET NX atomic-consume — one wins, the
 * other gets REFRESH_REPLAY, and the user sees a spurious logout.
 */
export class SingleFlightRefresh<T> {
  private inflight = new Map<string, Promise<T>>();

  /**
   * If a refresh keyed by this `key` (typically the current refresh JTI) is
   * already in flight, return its promise. Otherwise start one.
   */
  run(key: string, fn: () => Promise<T>): Promise<T> {
    const existing = this.inflight.get(key);
    if (existing) return existing;
    const promise = fn().finally(() => {
      // Clear the slot when the work finishes (success OR error). Subsequent
      // calls with the same key after this point will re-run.
      this.inflight.delete(key);
    });
    this.inflight.set(key, promise);
    return promise;
  }

  /** Number of in-flight refreshes (mostly for test assertions). */
  size(): number {
    return this.inflight.size;
  }
}

/**
 * Test/observability helper: extract the JTI from a refresh JWT WITHOUT
 * verifying it. NEVER use for security decisions — verify the token before
 * trusting any claim. Used purely as the single-flight key.
 */
export function readJtiUnsafe(token: string): string {
  const parts = token.split(".");
  if (parts.length !== 3) throw new AuthError("MALFORMED_TOKEN", "Token is not a JWT (3 parts)");
  try {
    const payload = JSON.parse(
      Buffer.from(parts[1]!.replace(/-/g, "+").replace(/_/g, "/"), "base64").toString("utf8"),
    ) as { jti?: string };
    if (typeof payload.jti !== "string") {
      throw new AuthError("MALFORMED_TOKEN", "Token payload missing jti");
    }
    return payload.jti;
  } catch (e) {
    if (e instanceof AuthError) throw e;
    throw new AuthError("MALFORMED_TOKEN", "Token payload is not valid JSON");
  }
}
