"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Shield, ShieldOff, LogOut, Edit } from "lucide-react";
import { apiGet, apiPost, apiPatch, API_URLS } from "@shared/lib";
import { TableSkeleton } from "@shared/components/skeleton";
import { EmptyState } from "@shared/components/empty-state";
import { ErrorFallback } from "@shared/components/error-boundary";
import { formatRelative, cn } from "@shared/lib/format";

interface UserRow {
  id: string;
  email: string;
  name: string;
  role: string;
  tenant_id: string;
  mfa_enrolled: boolean;
  active: boolean;
  last_login?: string;
  created_at: string;
}

const ROLE_COLORS: Record<string, string> = {
  admin: "bg-red-100 text-red-700 dark:bg-red-950/50 dark:text-red-400",
  billing_operator: "bg-blue-100 text-blue-700 dark:bg-blue-950/50 dark:text-blue-400",
  fwa_investigator: "bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-400",
  client_manager: "bg-green-100 text-green-700 dark:bg-green-950/50 dark:text-green-400",
  viewer: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-400",
};

export default function UsersPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [_selectedUser, setSelectedUser] = useState<UserRow | null>(null);

  const {
    data,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["admin-users"],
    queryFn: () =>
      apiGet<{ users: UserRow[] }>(`${API_URLS.corePlatform}/admin/users`),
    retry: 2,
  });

  const forceLogoutMutation = useMutation({
    mutationFn: (userId: string) =>
      apiPost(`${API_URLS.corePlatform}/admin/users/${userId}/force-logout`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
  });

  const toggleActiveMutation = useMutation({
    mutationFn: ({ userId, active }: { userId: string; active: boolean }) =>
      apiPatch(`${API_URLS.corePlatform}/admin/users/${userId}`, { active }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
  });

  const users = data?.users ?? [];
  const filtered = users.filter(
    (u) =>
      u.name.toLowerCase().includes(search.toLowerCase()) ||
      u.email.toLowerCase().includes(search.toLowerCase()) ||
      u.role.toLowerCase().includes(search.toLowerCase())
  );

  if (error) {
    return (
      <ErrorFallback
        error={error instanceof Error ? error : new Error("Failed to load users")}
        onRetry={() => queryClient.invalidateQueries({ queryKey: ["admin-users"] })}
      />
    );
  }

  return (
    <div className="max-w-7xl mx-auto">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">User Management</h1>
          <p className="text-sm text-muted-foreground">
            Manage operator accounts, roles, and MFA enrollment
          </p>
        </div>
        <button
          onClick={() => setSelectedUser({} as UserRow)}
          className="flex items-center gap-2 rounded-md bg-teal-500 px-4 py-2 text-sm font-medium text-white hover:bg-teal-600 transition-colors"
        >
          <Plus className="h-4 w-4" />
          New User
        </button>
      </div>

      {/* Search */}
      <div className="mb-4">
        <input
          type="search"
          placeholder="Search users by name, email, or role..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full max-w-md rounded-md border bg-card px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
          aria-label="Search users"
        />
      </div>

      {/* Table */}
      {isLoading ? (
        <TableSkeleton rows={8} cols={6} />
      ) : filtered.length === 0 ? (
        <EmptyState
          title="No users found"
          description={search ? `No users matching "${search}"` : "No users have been created yet."}
          action={{ label: "Create first user", onClick: () => setSelectedUser({} as UserRow) }}
        />
      ) : (
        <div className="overflow-hidden rounded-lg border bg-card">
          <div className="overflow-x-auto">
            <table className="w-full text-sm" aria-label="Users table">
              <thead className="border-b bg-muted/50">
                <tr>
                  <th scope="col" className="px-4 py-3 text-left font-medium">Name</th>
                  <th scope="col" className="px-4 py-3 text-left font-medium">Email</th>
                  <th scope="col" className="px-4 py-3 text-left font-medium">Role</th>
                  <th scope="col" className="px-4 py-3 text-left font-medium">MFA</th>
                  <th scope="col" className="px-4 py-3 text-left font-medium">Last Login</th>
                  <th scope="col" className="px-4 py-3 text-left font-medium">Status</th>
                  <th scope="col" className="px-4 py-3 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {filtered.map((user) => (
                  <tr key={user.id} className="hover:bg-muted/30 transition-colors">
                    <td className="px-4 py-3 font-medium">{user.name}</td>
                    <td className="px-4 py-3 text-muted-foreground">{user.email}</td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          "inline-flex rounded-full px-2 py-0.5 text-xs font-medium capitalize",
                          ROLE_COLORS[user.role] ?? "bg-muted"
                        )}
                      >
                        {user.role.replace("_", " ")}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {user.mfa_enrolled ? (
                        <span className="flex items-center gap-1 text-green-600 dark:text-green-400 text-xs">
                          <Shield className="h-3.5 w-3.5" /> Enrolled
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-amber-500 text-xs">
                          <ShieldOff className="h-3.5 w-3.5" /> Not enrolled
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground text-xs">
                      {user.last_login ? formatRelative(user.last_login) : "Never"}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          "inline-flex rounded-full px-2 py-0.5 text-xs font-medium",
                          user.active
                            ? "bg-green-100 text-green-700 dark:bg-green-950/50 dark:text-green-400"
                            : "bg-muted text-muted-foreground"
                        )}
                      >
                        {user.active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => setSelectedUser(user)}
                          className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                          aria-label={`Edit ${user.name}`}
                        >
                          <Edit className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick={() => forceLogoutMutation.mutate(user.id)}
                          disabled={forceLogoutMutation.isPending}
                          className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-destructive"
                          aria-label={`Force logout ${user.name}`}
                        >
                          <LogOut className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick={() => toggleActiveMutation.mutate({ userId: user.id, active: !user.active })}
                          disabled={toggleActiveMutation.isPending}
                          className={cn(
                            "rounded p-1 hover:bg-muted transition-colors",
                            user.active
                              ? "text-green-600 hover:text-red-500"
                              : "text-muted-foreground hover:text-green-600"
                          )}
                          aria-label={user.active ? `Deactivate ${user.name}` : `Activate ${user.name}`}
                        >
                          {user.active ? (
                            <Shield className="h-3.5 w-3.5" />
                          ) : (
                            <ShieldOff className="h-3.5 w-3.5" />
                          )}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* User count */}
      {!isLoading && filtered.length > 0 && (
        <p className="mt-3 text-xs text-muted-foreground">
          Showing {filtered.length} of {users.length} users
        </p>
      )}
    </div>
  );
}
