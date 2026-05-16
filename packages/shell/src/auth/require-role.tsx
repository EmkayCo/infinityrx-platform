import "server-only";
import type { ReactNode } from "react";
import { getSessionUser } from "./get-session-user.js";

// Exported so consumers can type wrappers without reaching into src/.
export interface RequireRoleProps {
  /**
   * Role names the authenticated user must possess ALL of.
   * An empty array means "any authenticated user is allowed."
   */
  roles: readonly string[];
  children: ReactNode;
  /** Rendered when the user lacks the required roles. Default: null (renders nothing). */
  fallback?: ReactNode;
}

/**
 * Granular role-based RSC gate.
 *
 * Requires a parent <RequireAuth> (or equivalent) to have already confirmed
 * a valid session exists. If the user is not authenticated, falls back.
 * If the user lacks ANY of the required roles, renders fallback (default: null).
 *
 * Usage:
 *   <RequireRole roles={["billing_admin", "platform_admin"]}>
 *     <BillingConfigPanel />
 *   </RequireRole>
 */
export async function RequireRole({
  roles,
  children,
  fallback = null,
}: RequireRoleProps): Promise<ReactNode> {
  const user = await getSessionUser();
  if (!user) return <>{fallback}</>;

  const hasAll = roles.every((r) => user.roles.includes(r));
  return hasAll ? <>{children}</> : <>{fallback}</>;
}
