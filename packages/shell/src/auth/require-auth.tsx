import "server-only";
import { redirect } from "next/navigation";
import type { ReactNode } from "react";
import { getSessionUser } from "./get-session-user.js";

// Exported so consumers can type wrappers without reaching into src/.
export interface RequireAuthProps {
  children: ReactNode;
  /** Path to redirect unauthenticated requests to. Default: "/login" */
  loginPath?: string;
  /** Current path, included as ?callbackUrl= on the redirect. */
  callbackUrl?: string;
}

/**
 * Server Component auth gate.
 *
 * Reads the session server-side via getSessionUser() (which calls next-auth's
 * auth()). If no valid session is found, redirects to loginPath with the
 * current path as callbackUrl. Authenticated users receive children; the
 * redirect happens before any HTML is sent — unauthorized users never see
 * guarded content, even briefly.
 *
 * Usage in app/(authenticated)/layout.tsx (RSC):
 *   <RequireAuth callbackUrl={pathname}>
 *     {children}
 *   </RequireAuth>
 */
export async function RequireAuth({
  children,
  loginPath = "/login",
  callbackUrl,
}: RequireAuthProps): Promise<ReactNode> {
  const user = await getSessionUser();
  if (!user) {
    const target = callbackUrl
      ? `${loginPath}?callbackUrl=${encodeURIComponent(callbackUrl)}`
      : loginPath;
    redirect(target);
  }
  return <>{children}</>;
}
