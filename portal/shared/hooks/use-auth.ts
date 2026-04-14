"use client";

import { useSession, signIn, signOut } from "next-auth/react";
import { Role, Permission, ROLE_PERMISSIONS } from "@shared/types/auth";

export interface UseAuthReturn {
  user: {
    id: string;
    email: string;
    name: string;
    role: Role;
    tenant_id: string;
    permissions: Permission[];
    mfa_enrolled: boolean;
  } | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  hasRole: (role: Role) => boolean;
  hasPermission: (permission: Permission) => boolean;
  signIn: typeof signIn;
  signOut: typeof signOut;
}

export function useAuth(): UseAuthReturn {
  const { data: session, status } = useSession();
  const isLoading = status === "loading";
  const isAuthenticated = status === "authenticated" && !!session?.user;

  const sessionUser = session?.user as
    | {
        id: string;
        email: string;
        name: string;
        role: string;
        tenant_id: string;
        permissions: string[];
        mfa_enrolled: boolean;
      }
    | undefined;

  const user = sessionUser
    ? {
        id: sessionUser.id,
        email: sessionUser.email,
        name: sessionUser.name ?? "",
        role: sessionUser.role as Role,
        tenant_id: sessionUser.tenant_id,
        permissions: (sessionUser.permissions ?? []) as Permission[],
        mfa_enrolled: sessionUser.mfa_enrolled ?? false,
      }
    : null;

  function isAdminRole(role: string | undefined): boolean {
    return role === Role.Admin || role === "platform_admin";
  }

  function hasRole(role: Role): boolean {
    if (!user) return false;
    return user.role === role || isAdminRole(user.role);
  }

  function hasPermission(permission: Permission): boolean {
    if (!user) return false;
    if (isAdminRole(user.role)) return true;
    if ((user.permissions as unknown as string[]).includes("*")) return true;
    if (user.permissions.includes(permission)) return true;
    const rolePerms = ROLE_PERMISSIONS[user.role] ?? [];
    return rolePerms.includes(permission);
  }

  return {
    user,
    isLoading,
    isAuthenticated,
    hasRole,
    hasPermission,
    signIn,
    signOut,
  };
}
