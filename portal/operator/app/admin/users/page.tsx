"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Shield, ShieldOff, LogOut, Edit, X } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPost, apiPut, API_URLS } from "@shared/lib";
import { ApiClientError } from "@shared/lib/api-client";
import { TableSkeleton } from "@shared/components/skeleton";
import { EmptyState } from "@shared/components/empty-state";
import { ErrorFallback } from "@shared/components/error-boundary";
import { formatRelative, cn } from "@shared/lib/format";

// The backend `POST /users` contract (modules/core-platform/src/auth/schemas.py
// `UserCreate`) expects email, display_name, password, role_names. The display
// name is joined from the first/last name fields in the modal form.
interface CreateUserRequest {
  email: string;
  display_name: string;
  password: string;
  role_names: string[];
}

// Dropdown options. `platform_admin` is seeded by `seed_system_roles`; the
// other three are frontend role conventions and must exist in the backend's
// roles table (either via `SYSTEM_ROLE_NAMES` or a tenant-scoped custom
// role) for creation to succeed. If the backend rejects with "role not
// found", the toast surfaces the exact missing name.
const ROLE_OPTIONS: { value: string; label: string }[] = [
  { value: "platform_admin", label: "Platform admin" },
  { value: "billing_operator", label: "Billing operator" },
  { value: "fwa_investigator", label: "FWA investigator" },
  { value: "viewer", label: "Viewer" },
];

interface NewUserForm {
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  password: string;
  confirm_password: string;
}

const EMPTY_FORM: NewUserForm = {
  email: "",
  first_name: "",
  last_name: "",
  role: "platform_admin",
  password: "",
  confirm_password: "",
};

// Wire-shape returned by `GET /users` on core-platform
// (`modules/core-platform/src/auth/schemas.py`, `UserResponse`). Kept
// intentionally identical to the backend so there's no translation layer
// hiding divergence. Optional fields account for older mocks or partial
// responses.
interface BackendUser {
  id: string;
  tenant_id: string;
  email: string;
  display_name: string;
  status: "active" | "inactive" | "locked" | string;
  last_login_at: string | null;
  failed_login_count: number;
  mfa_enabled?: boolean;
  created_at?: string | null;
  roles: string[];
}

// View-model used by the table renderer. Everything the UI reads comes from
// here so field-name drift stays contained to `toViewModel` below.
interface UserVM {
  id: string;
  email: string;
  displayName: string;
  primaryRole: string;
  allRoles: string[];
  mfaEnrolled: boolean;
  active: boolean;
  locked: boolean;
  lastLogin: string | null;
}

function toViewModel(u: BackendUser): UserVM {
  return {
    id: u.id,
    email: u.email,
    displayName: u.display_name ?? "",
    primaryRole: u.roles?.[0] ?? "—",
    allRoles: u.roles ?? [],
    mfaEnrolled: Boolean(u.mfa_enabled),
    active: u.status === "active",
    locked: u.status === "locked",
    lastLogin: u.last_login_at ?? null,
  };
}

const ROLE_COLORS: Record<string, string> = {
  platform_admin: "bg-red-100 text-red-700 dark:bg-red-950/50 dark:text-red-400",
  tenant_admin: "bg-red-100 text-red-700 dark:bg-red-950/50 dark:text-red-400",
  billing_operator: "bg-blue-100 text-blue-700 dark:bg-blue-950/50 dark:text-blue-400",
  fwa_investigator: "bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-400",
  directory_admin: "bg-teal-100 text-teal-700 dark:bg-teal-950/50 dark:text-teal-400",
  edi_operator: "bg-cyan-100 text-cyan-700 dark:bg-cyan-950/50 dark:text-cyan-400",
  clinical_reviewer: "bg-purple-100 text-purple-700 dark:bg-purple-950/50 dark:text-purple-400",
  report_viewer: "bg-indigo-100 text-indigo-700 dark:bg-indigo-950/50 dark:text-indigo-400",
  client_admin: "bg-green-100 text-green-700 dark:bg-green-950/50 dark:text-green-400",
  viewer: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-400",
  tenant_viewer: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-400",
};

export default function UsersPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState<NewUserForm>(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);

  function openModal() {
    setForm(EMPTY_FORM);
    setFormError(null);
    setModalOpen(true);
  }

  function closeModal() {
    setModalOpen(false);
    setFormError(null);
  }

  const createUserMutation = useMutation({
    // POST /api/v1/users — matches the backend `user_router.create`
    // endpoint (mounted under the aggregator router at /api/v1) and the
    // `UserCreate` schema. The response is a `UserResponse` we feed
    // straight back through the query invalidation below.
    mutationFn: (body: CreateUserRequest) =>
      apiPost<BackendUser>(`${API_URLS.corePlatform}/api/v1/users`, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      toast.success("User created");
      closeModal();
    },
    onError: (err) => {
      const msg =
        err instanceof ApiClientError
          ? err.message
          : err instanceof Error
            ? err.message
            : "Failed to create user";
      setFormError(msg);
      toast.error(msg);
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);

    const first = form.first_name.trim();
    const last = form.last_name.trim();
    const email = form.email.trim().toLowerCase();

    if (!email || !first || !last) {
      setFormError("Email, first name, and last name are required.");
      return;
    }
    // Rough shape check — backend uses EmailStr for the authoritative validation.
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setFormError("Enter a valid email address.");
      return;
    }
    if (form.password.length < 8) {
      setFormError("Password must be at least 8 characters.");
      return;
    }
    if (form.password !== form.confirm_password) {
      setFormError("Passwords do not match.");
      return;
    }

    createUserMutation.mutate({
      email,
      display_name: `${first} ${last}`,
      password: form.password,
      role_names: [form.role],
    });
  }

  const {
    data,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["admin-users"],
    // The backend `GET /api/v1/users` returns `list[UserResponse]` at the
    // top level (no wrapper). Accept either shape so legacy mocks that
    // still return `{ users: [...] }` continue to work during the
    // transition.
    queryFn: async () => {
      const raw = await apiGet<BackendUser[] | { users: BackendUser[] }>(
        `${API_URLS.corePlatform}/api/v1/users`
      );
      return Array.isArray(raw) ? raw : (raw?.users ?? []);
    },
    retry: 2,
  });

  // Real backend uses `POST /api/v1/users/{id}/lock` to force a session
  // termination by locking the account. There is no separate force-logout
  // endpoint.
  const lockMutation = useMutation({
    mutationFn: (userId: string) =>
      apiPost(`${API_URLS.corePlatform}/api/v1/users/${userId}/lock`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      toast.success("User locked");
    },
    onError: (err) => {
      toast.error(
        err instanceof Error ? err.message : "Failed to lock user"
      );
    },
  });

  // Toggle active ⇄ inactive via `PUT /api/v1/users/{id}` with a `status`
  // patch. The backend accepts status values `active | inactive | locked`.
  const toggleActiveMutation = useMutation({
    mutationFn: ({ userId, nextStatus }: { userId: string; nextStatus: "active" | "inactive" }) =>
      apiPut(`${API_URLS.corePlatform}/api/v1/users/${userId}`, { status: nextStatus }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
    onError: (err) => {
      toast.error(
        err instanceof Error ? err.message : "Failed to update user"
      );
    },
  });

  const users: UserVM[] = (data ?? []).map(toViewModel);
  const q = search.toLowerCase();
  const filtered = users.filter(
    (u) =>
      u.displayName.toLowerCase().includes(q) ||
      u.email.toLowerCase().includes(q) ||
      u.allRoles.some((r) => r.toLowerCase().includes(q))
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
          onClick={openModal}
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
          action={{ label: "Create first user", onClick: openModal }}
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
                    <td className="px-4 py-3 font-medium">{user.displayName}</td>
                    <td className="px-4 py-3 text-muted-foreground">{user.email}</td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          "inline-flex rounded-full px-2 py-0.5 text-xs font-medium capitalize",
                          ROLE_COLORS[user.primaryRole] ?? "bg-muted"
                        )}
                        title={user.allRoles.join(", ")}
                      >
                        {user.primaryRole.replace(/_/g, " ")}
                        {user.allRoles.length > 1 && (
                          <span className="ml-1 opacity-60">+{user.allRoles.length - 1}</span>
                        )}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {user.mfaEnrolled ? (
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
                      {user.lastLogin ? formatRelative(user.lastLogin) : "Never"}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          "inline-flex rounded-full px-2 py-0.5 text-xs font-medium",
                          user.locked
                            ? "bg-red-100 text-red-700 dark:bg-red-950/50 dark:text-red-400"
                            : user.active
                              ? "bg-green-100 text-green-700 dark:bg-green-950/50 dark:text-green-400"
                              : "bg-muted text-muted-foreground"
                        )}
                      >
                        {user.locked ? "Locked" : user.active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() =>
                            toast.info(
                              "Editing existing users is not implemented yet — use the API directly."
                            )
                          }
                          className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                          aria-label={`Edit ${user.displayName}`}
                        >
                          <Edit className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick={() => lockMutation.mutate(user.id)}
                          disabled={lockMutation.isPending || user.locked}
                          className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-destructive disabled:opacity-40"
                          aria-label={`Lock ${user.displayName}`}
                          title="Lock account (terminates sessions)"
                        >
                          <LogOut className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick={() =>
                            toggleActiveMutation.mutate({
                              userId: user.id,
                              nextStatus: user.active ? "inactive" : "active",
                            })
                          }
                          disabled={toggleActiveMutation.isPending || user.locked}
                          className={cn(
                            "rounded p-1 hover:bg-muted transition-colors disabled:opacity-40",
                            user.active
                              ? "text-green-600 hover:text-red-500"
                              : "text-muted-foreground hover:text-green-600"
                          )}
                          aria-label={user.active ? `Deactivate ${user.displayName}` : `Activate ${user.displayName}`}
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

      {modalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="new-user-title"
          onClick={(e) => {
            if (e.target === e.currentTarget && !createUserMutation.isPending) {
              closeModal();
            }
          }}
        >
          <div className="w-full max-w-md rounded-lg border bg-card shadow-xl">
            <div className="flex items-center justify-between border-b px-5 py-3">
              <h2 id="new-user-title" className="text-base font-semibold">
                New user
              </h2>
              <button
                onClick={closeModal}
                disabled={createUserMutation.isPending}
                className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-40"
                aria-label="Close"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4 px-5 py-4">
              <div>
                <label
                  htmlFor="new-user-email"
                  className="mb-1 block text-xs font-medium text-muted-foreground"
                >
                  Email
                </label>
                <input
                  id="new-user-email"
                  type="email"
                  autoComplete="off"
                  value={form.email}
                  onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                  className="w-full rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label
                    htmlFor="new-user-first"
                    className="mb-1 block text-xs font-medium text-muted-foreground"
                  >
                    First name
                  </label>
                  <input
                    id="new-user-first"
                    type="text"
                    autoComplete="off"
                    value={form.first_name}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, first_name: e.target.value }))
                    }
                    className="w-full rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
                    required
                  />
                </div>
                <div>
                  <label
                    htmlFor="new-user-last"
                    className="mb-1 block text-xs font-medium text-muted-foreground"
                  >
                    Last name
                  </label>
                  <input
                    id="new-user-last"
                    type="text"
                    autoComplete="off"
                    value={form.last_name}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, last_name: e.target.value }))
                    }
                    className="w-full rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
                    required
                  />
                </div>
              </div>

              <div>
                <label
                  htmlFor="new-user-role"
                  className="mb-1 block text-xs font-medium text-muted-foreground"
                >
                  Role
                </label>
                <select
                  id="new-user-role"
                  value={form.role}
                  onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}
                  className="w-full rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
                >
                  {ROLE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label
                  htmlFor="new-user-password"
                  className="mb-1 block text-xs font-medium text-muted-foreground"
                >
                  Password
                </label>
                <input
                  id="new-user-password"
                  type="password"
                  autoComplete="new-password"
                  minLength={8}
                  value={form.password}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, password: e.target.value }))
                  }
                  className="w-full rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
                  required
                />
                <p className="mt-1 text-xs text-muted-foreground">
                  Minimum 8 characters.
                </p>
              </div>

              <div>
                <label
                  htmlFor="new-user-password-confirm"
                  className="mb-1 block text-xs font-medium text-muted-foreground"
                >
                  Confirm password
                </label>
                <input
                  id="new-user-password-confirm"
                  type="password"
                  autoComplete="new-password"
                  minLength={8}
                  value={form.confirm_password}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, confirm_password: e.target.value }))
                  }
                  className="w-full rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
                  required
                />
              </div>

              {formError && (
                <div
                  className="rounded-md border border-red-500/30 bg-red-500/5 px-3 py-2 text-xs text-red-500"
                  role="alert"
                >
                  {formError}
                </div>
              )}

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={closeModal}
                  disabled={createUserMutation.isPending}
                  className="rounded-md border px-3 py-2 text-sm hover:bg-muted disabled:opacity-40"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createUserMutation.isPending}
                  className="rounded-md bg-teal-500 px-4 py-2 text-sm font-medium text-white hover:bg-teal-600 disabled:opacity-40"
                >
                  {createUserMutation.isPending ? "Creating…" : "Create user"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
