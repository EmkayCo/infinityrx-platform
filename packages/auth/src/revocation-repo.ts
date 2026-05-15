/**
 * Per SD-1 §8.5. The runtime implementation talks to Redis; tests use an
 * in-memory impl. The auth package only defines the interface — backend Python
 * code (out of SP-0 scope) implements the Redis client.
 *
 * Three key families:
 *   - `auth:revoked:<jti>`  — explicit revocation (logout / admin)
 *   - `auth:consumed:<jti>` — refresh-token atomic consume (set via SET NX)
 *   - `auth:tokens_valid_since:<sub>` — per-user cutoff (password reset / disable)
 */
export interface RevocationRepo {
  /** Check whether a jti is in the revoked set. */
  isRevoked(jti: string): Promise<boolean>;

  /** Atomic consume: returns true if THIS caller set the key (SET NX won), false if already-consumed (replay). */
  consumeRefresh(jti: string, reason: string, ttlSeconds: number): Promise<boolean>;

  /** Read the tokens_valid_since cutoff for a user, or null if no cutoff is set. */
  getTokensValidSince(sub: string): Promise<number | null>;

  /** Write the per-user cutoff (password reset / disable). */
  setTokensValidSince(sub: string, unixSeconds: number): Promise<void>;

  /** Mark a jti as revoked (logout / admin). */
  revoke(jti: string, reason: string, ttlSeconds: number): Promise<void>;
}

/**
 * In-memory implementation for tests. NEVER use in production — no durability,
 * no cross-process consistency.
 */
export class InMemoryRevocationRepo implements RevocationRepo {
  private readonly revoked = new Map<string, { reason: string; expiresAt: number }>();
  private readonly consumed = new Map<string, { reason: string; expiresAt: number }>();
  private readonly tokensValidSince = new Map<string, number>();

  private now(): number {
    return Math.floor(Date.now() / 1000);
  }

  async isRevoked(jti: string): Promise<boolean> {
    const entry = this.revoked.get(jti);
    if (!entry) return false;
    if (entry.expiresAt < this.now()) {
      this.revoked.delete(jti);
      return false;
    }
    return true;
  }

  async consumeRefresh(jti: string, reason: string, ttlSeconds: number): Promise<boolean> {
    if (this.consumed.has(jti)) {
      const entry = this.consumed.get(jti)!;
      if (entry.expiresAt >= this.now()) return false;
      this.consumed.delete(jti);
    }
    this.consumed.set(jti, { reason, expiresAt: this.now() + ttlSeconds });
    return true;
  }

  async getTokensValidSince(sub: string): Promise<number | null> {
    return this.tokensValidSince.get(sub) ?? null;
  }

  async setTokensValidSince(sub: string, unixSeconds: number): Promise<void> {
    this.tokensValidSince.set(sub, unixSeconds);
  }

  async revoke(jti: string, reason: string, ttlSeconds: number): Promise<void> {
    this.revoked.set(jti, { reason, expiresAt: this.now() + ttlSeconds });
  }
}
