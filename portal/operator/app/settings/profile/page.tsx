"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation } from "@tanstack/react-query";
import { Save, Shield } from "lucide-react";
import { apiPatch } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import { useAuth } from "@shared/hooks/use-auth";
import { cn } from "@shared/lib/format";
import { toast } from "sonner";

const profileSchema = z.object({
  name: z.string().min(2, "Name must be at least 2 characters"),
  email: z.string().email("Enter a valid email address"),
});

type ProfileForm = z.infer<typeof profileSchema>;

export default function ProfileSettingsPage() {
  const { user } = useAuth();

  const {
    register,
    handleSubmit,
    formState: { errors, isDirty },
  } = useForm<ProfileForm>({
    resolver: zodResolver(profileSchema),
    values: {
      name: user?.name ?? "",
      email: user?.email ?? "",
    },
  });

  const saveMutation = useMutation({
    mutationFn: (data: ProfileForm) =>
      apiPatch(`${API_URLS.corePlatform}/users/me`, data),
    onSuccess: () => {
      toast.success("Profile updated successfully");
    },
    onError: () => {
      toast.error("Failed to update profile");
    },
  });

  return (
    <div>
      <h2 className="text-base font-semibold mb-6">Profile</h2>

      <form onSubmit={handleSubmit((d) => saveMutation.mutate(d))} className="space-y-4">
        {/* Avatar */}
        <div className="flex items-center gap-4">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-teal-500 text-2xl font-bold text-white">
            {user?.name?.charAt(0)?.toUpperCase() ?? "?"}
          </div>
          <div>
            <p className="font-medium">{user?.name}</p>
            <p className="text-sm text-muted-foreground capitalize">
              {user?.role?.replace("_", " ")}
            </p>
          </div>
        </div>

        {/* Name */}
        <div>
          <label htmlFor="name" className="block text-sm font-medium mb-1.5">
            Full name
          </label>
          <input
            id="name"
            type="text"
            {...register("name")}
            className={cn(
              "w-full rounded-md border bg-card px-3 py-2 text-sm",
              "focus:outline-none focus:ring-2 focus:ring-teal-500 transition-colors",
              errors.name ? "border-destructive" : ""
            )}
            aria-invalid={!!errors.name}
          />
          {errors.name && (
            <p className="mt-1 text-xs text-destructive" role="alert">{errors.name.message}</p>
          )}
        </div>

        {/* Email */}
        <div>
          <label htmlFor="email" className="block text-sm font-medium mb-1.5">
            Email address
          </label>
          <input
            id="email"
            type="email"
            {...register("email")}
            className={cn(
              "w-full rounded-md border bg-card px-3 py-2 text-sm",
              "focus:outline-none focus:ring-2 focus:ring-teal-500 transition-colors",
              errors.email ? "border-destructive" : ""
            )}
            aria-invalid={!!errors.email}
          />
          {errors.email && (
            <p className="mt-1 text-xs text-destructive" role="alert">{errors.email.message}</p>
          )}
        </div>

        {/* MFA status */}
        <div className="rounded-lg border p-4 flex items-center gap-3">
          <Shield
            className={cn(
              "h-5 w-5 shrink-0",
              user?.mfa_enrolled ? "text-green-500" : "text-amber-500"
            )}
          />
          <div className="flex-1">
            <p className="font-medium text-sm">Two-Factor Authentication</p>
            <p className="text-xs text-muted-foreground">
              {user?.mfa_enrolled
                ? "MFA is enrolled. Your account is protected."
                : "MFA is not enrolled. Set it up to protect your account."}
            </p>
          </div>
          {!user?.mfa_enrolled && (
            <button
              type="button"
              className="rounded-md bg-amber-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-amber-600 transition-colors"
            >
              Set up MFA
            </button>
          )}
        </div>

        <div className="flex justify-end pt-2">
          <button
            type="submit"
            disabled={!isDirty || saveMutation.isPending}
            className="flex items-center gap-2 rounded-md bg-teal-500 px-4 py-2 text-sm font-medium text-white hover:bg-teal-600 disabled:opacity-50 transition-colors"
          >
            <Save className="h-4 w-4" />
            {saveMutation.isPending ? "Saving..." : "Save changes"}
          </button>
        </div>
      </form>
    </div>
  );
}
