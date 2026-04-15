"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { signIn } from "next-auth/react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Eye, EyeOff, ShieldCheck, FlaskConical } from "lucide-react";
import { cn } from "@shared/lib/format";
import { IfxLogo } from "@/components/ui/ifx-logo";

const DEV_BYPASS_VISIBLE =
  process.env.NODE_ENV !== "production" &&
  process.env.NEXT_PUBLIC_DEV_AUTH_BYPASS === "true";

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
    <div className="flex min-h-screen items-center justify-center bg-ifx-gray-50 px-4">
      {/* Subtle wave pattern background */}
      <div
        aria-hidden="true"
        className="pointer-events-none fixed inset-0 opacity-[0.04]"
        style={{
          backgroundImage:
            "radial-gradient(circle at 20% 30%, var(--ifx-navy) 0%, transparent 40%), radial-gradient(circle at 80% 70%, var(--ifx-blue) 0%, transparent 40%)",
        }}
      />

      <div className="relative w-full max-w-sm">
        {/* Logo — fill swaps with theme: #0B1120 light, white dark */}
        <div className="mb-8 flex flex-col items-center">
          <IfxLogo
            variant="theme"
            size="xl"
            showWordmark
            className="text-[#0B1120] dark:text-white"
          />
        </div>

        {/* Card */}
        <div className="rounded-xl border border-ifx-gray-100 bg-white p-8 shadow-[0_4px_24px_rgba(13,9,54,0.08)]">
          <h2 className="mb-6 text-center text-lg font-bold text-ifx-gray-900">
            Sign in to your account
          </h2>

          <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
            {/* Email */}
            <div>
              <label
                htmlFor="email"
                className="mb-1.5 block text-sm font-medium text-ifx-gray-700"
              >
                Email address
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                {...register("email")}
                className={cn(
                  "w-full rounded-md border bg-white px-3 py-2.5 text-sm text-ifx-gray-900 placeholder:text-ifx-gray-400",
                  "focus:outline-none focus:ring-2 focus:ring-ifx-blue/40 focus:border-ifx-blue transition-colors",
                  errors.email ? "border-ifx-error" : "border-ifx-gray-100"
                )}
                placeholder="operator@infinityrx.com"
                aria-describedby={errors.email ? "email-error" : undefined}
                aria-invalid={!!errors.email}
              />
              {errors.email && (
                <p id="email-error" className="mt-1 text-xs text-ifx-error" role="alert">
                  {errors.email.message}
                </p>
              )}
            </div>

            {/* Password */}
            <div>
              <label
                htmlFor="password"
                className="mb-1.5 block text-sm font-medium text-ifx-gray-700"
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
                    "w-full rounded-md border bg-white px-3 py-2.5 pr-10 text-sm text-ifx-gray-900",
                    "focus:outline-none focus:ring-2 focus:ring-ifx-blue/40 focus:border-ifx-blue transition-colors",
                    errors.password ? "border-ifx-error" : "border-ifx-gray-100"
                  )}
                  placeholder="Enter your password"
                  aria-describedby={errors.password ? "password-error" : undefined}
                  aria-invalid={!!errors.password}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((s) => !s)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-ifx-gray-400 hover:text-ifx-gray-700 transition-colors"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {errors.password && (
                <p id="password-error" className="mt-1 text-xs text-ifx-error" role="alert">
                  {errors.password.message}
                </p>
              )}
            </div>

            {authError && (
              <div
                className="flex items-center gap-2 rounded-md border border-ifx-error/20 bg-ifx-error-light px-3 py-2.5"
                role="alert"
              >
                <ShieldCheck className="h-4 w-4 text-ifx-error shrink-0" />
                <p className="text-sm text-ifx-error">{authError}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={isLoading}
              className={cn(
                "ifx-on-dark mt-2 w-full rounded-md bg-ifx-navy px-4 py-2.5 text-sm font-semibold text-white",
                "hover:bg-ifx-navy-dark focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ifx-blue",
                "disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              )}
            >
              {isLoading ? "Signing in..." : "Sign in"}
            </button>
          </form>

          {DEV_BYPASS_VISIBLE && (
            <div className="mt-6 border-t border-ifx-gray-100 pt-4">
              <button
                type="button"
                onClick={async () => {
                  setAuthError(null);
                  setIsLoading(true);
                  try {
                    const result = await signIn("dev-bypass", {
                      redirect: false,
                    });
                    if (result?.error) {
                      setAuthError(
                        "Dev bypass refused. Server flag DEV_AUTH_BYPASS is not set to 'true'."
                      );
                      return;
                    }
                    router.push(callbackUrl);
                  } finally {
                    setIsLoading(false);
                  }
                }}
                disabled={isLoading}
                className={cn(
                  "flex w-full items-center justify-center gap-2 rounded-md border border-ifx-warning/40 bg-ifx-warning-light px-4 py-2.5",
                  "text-sm font-medium text-ifx-warning hover:bg-ifx-warning-light/70",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ifx-warning",
                  "disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                )}
              >
                <FlaskConical className="h-4 w-4" />
                Sign in as Dev Admin (mock)
              </button>
              <p className="mt-2 text-center text-[11px] text-ifx-warning/70">
                Dev-only bypass. Disabled in production builds.
              </p>
            </div>
          )}
        </div>

        <p className="mt-6 text-center text-xs text-ifx-gray-500">
          Having trouble? Contact your system administrator.
        </p>
      </div>
    </div>
  );
}
