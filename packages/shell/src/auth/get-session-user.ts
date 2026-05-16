import "server-only";
// Import `auth` from the auth.config binding, not from "next-auth" directly.
// This ensures we use the configured session callback that populates
// sub/tid/roles/mfaEnrolled from Plan B's verifyAccessToken chain.
// See auth.config.ts for the load-bearing boundary documentation.
import { auth } from "./auth.config.js";
import type { SessionUser } from "./types.js";

/**
 * Returns the authenticated user identity from the current request's
 * server-side session, or null if no valid session is present.
 *
 * Must only be called from RSCs or Next.js route handlers.
 * The `server-only` import at the top of this file prevents it from
 * being accidentally imported in client components.
 */
export async function getSessionUser(): Promise<SessionUser> {
  const session = await auth();
  if (!session?.user) return null;

  const { sub, tid, roles, mfaEnrolled } = session.user as {
    sub?: string;
    tid?: string;
    roles?: string[];
    mfaEnrolled?: boolean;
  };

  if (!sub || !tid || !Array.isArray(roles)) return null;

  return {
    sub,
    tid,
    roles: roles as readonly string[],
    mfaEnrolled: mfaEnrolled ?? false,
  };
}
