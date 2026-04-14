"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { signIn } from "next-auth/react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Eye, EyeOff, ShieldCheck } from "lucide-react";
import { cn } from "@shared/lib/format";

const loginSchema = z.object({
  email: z.string().email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});

type LoginForm = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const callbackUrl = searchParams.get("callbackUrl") ?? "/";
  const [showPassword, setShowPassword] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
  });

  async function onSubmit(data: LoginForm) {
    setAuthError(null);
    setIsLoading(true);

    try {
      const result = await signIn("credentials", {
        email: data.email,
        password: data.password,
        redirect: false,
      });

      if (result?.error) {
        setAuthError("Invalid email or password. Please try again.");
        return;
      }

      // Check if MFA is required
      if (result?.url?.includes("mfa_required")) {
        router.push("/mfa");
        return;
      }

      router.push(callbackUrl);
    } catch {
      setAuthError("An unexpected error occurred. Please try again.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-navy-900 px-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="mb-8 flex flex-col items-center gap-3">
          <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-teal-500 shadow-lg">
            <span className="text-2xl font-bold text-white">IFX</span>
          </div>
          <div className="text-center">
            <h1 className="text-2xl font-bold text-white">InfinityRx</h1>
            <p className="mt-1 text-sm text-slate-400">Operator Portal</p>
          </div>
        </div>

        {/* Card */}
        <div className="rounded-xl border border-navy-700 bg-navy-800/50 p-8 shadow-xl backdrop-blur-sm">
          <h2 className="mb-6 text-center text-lg font-semibold text-white">
            Sign in to your account
          </h2>

          <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
            {/* Email */}
            <div>
              <label
                htmlFor="email"
                className="mb-1.5 block text-sm font-medium text-slate-300"
              >
                Email address
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                {...register("email")}
                className={cn(
                  "w-full rounded-md border bg-navy-900 px-3 py-2.5 text-sm text-white placeholder:text-slate-500",
                  "focus:outline-none focus:ring-2 focus:ring-teal-500/40 focus:border-teal-500 transition-colors",
                  errors.email ? "border-red-500" : "border-navy-600"
                )}
                placeholder="operator@infinityrx.com"
                aria-describedby={errors.email ? "email-error" : undefined}
                aria-invalid={!!errors.email}
              />
              {errors.email && (
                <p id="email-error" className="mt-1 text-xs text-red-400" role="alert">
                  {errors.email.message}
                </p>
              )}
            </div>

            {/* Password */}
            <div>
              <label
                htmlFor="password"
                className="mb-1.5 block text-sm font-medium text-slate-300"
              >
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  {...register("password")}
                  className={cn(
                    "w-full rounded-md border bg-navy-900 px-3 py-2.5 pr-10 text-sm text-white",
                    "focus:outline-none focus:ring-2 focus:ring-teal-500/40 focus:border-teal-500 transition-colors",
                    errors.password ? "border-red-500" : "border-navy-600"
                  )}
                  placeholder="Enter your password"
                  aria-describedby={errors.password ? "password-error" : undefined}
                  aria-invalid={!!errors.password}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((s) => !s)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200 transition-colors"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {errors.password && (
                <p id="password-error" className="mt-1 text-xs text-red-400" role="alert">
                  {errors.password.message}
                </p>
              )}
            </div>

            {/* Auth error */}
            {authError && (
              <div
                className="flex items-center gap-2 rounded-md border border-red-500/20 bg-red-500/10 px-3 py-2.5"
                role="alert"
              >
                <ShieldCheck className="h-4 w-4 text-red-400 shrink-0" />
                <p className="text-sm text-red-400">{authError}</p>
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={isLoading}
              className={cn(
                "mt-2 w-full rounded-md bg-teal-500 px-4 py-2.5 text-sm font-semibold text-white",
                "hover:bg-teal-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500",
                "disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              )}
            >
              {isLoading ? "Signing in..." : "Sign in"}
            </button>
          </form>
        </div>

        <p className="mt-6 text-center text-xs text-slate-500">
          Having trouble? Contact your system administrator.
        </p>
      </div>
    </div>
  );
}
