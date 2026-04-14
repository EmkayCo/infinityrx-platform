"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { signIn, useSession } from "next-auth/react";
import { ShieldCheck, KeyRound, Fingerprint } from "lucide-react";
import { cn } from "@shared/lib/format";

const CODE_LENGTH = 6;

export default function MFAPage() {
  const router = useRouter();
  const { data: session } = useSession();
  const [code, setCode] = useState<string[]>(Array(CODE_LENGTH).fill(""));
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  const challengeToken = (session as Record<string, unknown> | null)?.mfa_challenge_token as string | undefined;

  useEffect(() => {
    inputRefs.current[0]?.focus();
  }, []);

  async function verifyCode(fullCode: string) {
    if (!challengeToken) {
      setError("Session expired. Please sign in again.");
      router.push("/login");
      return;
    }

    setError(null);
    setIsLoading(true);

    try {
      const result = await signIn("mfa", {
        challenge_token: challengeToken,
        code: fullCode,
        redirect: false,
      });

      if (result?.error) {
        setError("Invalid verification code. Please try again.");
        setCode(Array(CODE_LENGTH).fill(""));
        inputRefs.current[0]?.focus();
        return;
      }

      router.push("/");
    } catch {
      setError("An unexpected error occurred. Please try again.");
    } finally {
      setIsLoading(false);
    }
  }

  function handleInput(index: number, value: string) {
    // Only allow digits
    const digit = value.replace(/\D/g, "").slice(-1);
    const newCode = [...code];
    newCode[index] = digit;
    setCode(newCode);

    // Auto-advance focus
    if (digit && index < CODE_LENGTH - 1) {
      inputRefs.current[index + 1]?.focus();
    }

    // Auto-submit when all digits entered
    if (newCode.every((d) => d !== "") && newCode.length === CODE_LENGTH) {
      verifyCode(newCode.join(""));
    }
  }

  function handleKeyDown(index: number, e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Backspace" && !code[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
    if (e.key === "ArrowLeft" && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
    if (e.key === "ArrowRight" && index < CODE_LENGTH - 1) {
      inputRefs.current[index + 1]?.focus();
    }
  }

  function handlePaste(e: React.ClipboardEvent) {
    e.preventDefault();
    const pasted = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, CODE_LENGTH);
    if (pasted) {
      const newCode = [...Array(CODE_LENGTH).fill("")];
      pasted.split("").forEach((digit, i) => {
        newCode[i] = digit;
      });
      setCode(newCode);
      if (newCode.every((d) => d !== "")) {
        verifyCode(newCode.join(""));
      } else {
        const nextEmpty = newCode.findIndex((d) => d === "");
        inputRefs.current[nextEmpty >= 0 ? nextEmpty : CODE_LENGTH - 1]?.focus();
      }
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
            <h1 className="text-2xl font-bold text-white">Two-Factor Authentication</h1>
            <p className="mt-1 text-sm text-slate-400">
              Enter the 6-digit code from your authenticator app
            </p>
          </div>
        </div>

        {/* Card */}
        <div className="rounded-xl border border-navy-700 bg-navy-800/50 p-8 shadow-xl backdrop-blur-sm">
          <div className="mb-6 flex justify-center">
            <ShieldCheck className="h-12 w-12 text-teal-400" />
          </div>

          {/* TOTP inputs */}
          <div
            className="flex gap-2 justify-center mb-6"
            role="group"
            aria-label="6-digit verification code"
          >
            {code.map((digit, i) => (
              <input
                key={i}
                ref={(el) => { inputRefs.current[i] = el; }}
                type="text"
                inputMode="numeric"
                pattern="[0-9]"
                maxLength={1}
                value={digit}
                onChange={(e) => handleInput(i, e.target.value)}
                onKeyDown={(e) => handleKeyDown(i, e)}
                onPaste={handlePaste}
                disabled={isLoading}
                aria-label={`Digit ${i + 1} of ${CODE_LENGTH}`}
                className={cn(
                  "w-11 h-13 text-center text-xl font-bold font-mono rounded-md border bg-navy-900 text-white",
                  "focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-teal-500 transition-colors",
                  "disabled:opacity-50",
                  digit ? "border-teal-500/60" : "border-navy-600",
                  error && "border-red-500"
                )}
                style={{ height: "3.25rem" }}
              />
            ))}
          </div>

          {/* Status / error */}
          {isLoading && (
            <div className="mb-4 text-center text-sm text-teal-400">
              Verifying...
            </div>
          )}
          {error && (
            <div
              className="mb-4 flex items-center gap-2 rounded-md border border-red-500/20 bg-red-500/10 px-3 py-2.5"
              role="alert"
            >
              <ShieldCheck className="h-4 w-4 text-red-400 shrink-0" />
              <p className="text-sm text-red-400">{error}</p>
            </div>
          )}

          {/* Submit button */}
          <button
            onClick={() => {
              const full = code.join("");
              if (full.length === CODE_LENGTH) verifyCode(full);
            }}
            disabled={isLoading || code.some((d) => d === "")}
            className={cn(
              "w-full rounded-md bg-teal-500 px-4 py-2.5 text-sm font-semibold text-white",
              "hover:bg-teal-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500",
              "disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
            )}
          >
            <KeyRound className="h-4 w-4" />
            {isLoading ? "Verifying..." : "Verify"}
          </button>

          {/* FIDO2 fallback */}
          <div className="mt-4 border-t border-navy-700 pt-4">
            <button
              type="button"
              disabled
              className="flex w-full items-center justify-center gap-2 rounded-md border border-navy-600 px-4 py-2.5 text-sm text-slate-400 opacity-60 cursor-not-allowed"
              aria-label="Use security key (not available in this environment)"
            >
              <Fingerprint className="h-4 w-4" />
              Use security key (FIDO2)
            </button>
            <p className="mt-2 text-center text-xs text-slate-500">
              Hardware key support requires a compatible browser
            </p>
          </div>
        </div>

        <p className="mt-6 text-center text-xs text-slate-500">
          Can&apos;t access your authenticator?{" "}
          <a href="/login" className="text-teal-400 hover:underline">
            Back to sign in
          </a>
        </p>
      </div>
    </div>
  );
}
