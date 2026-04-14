"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useSession, signOut } from "next-auth/react";
import { ShieldAlert } from "lucide-react";
import { SESSION_CONFIG } from "@shared/lib/constants";

const EVENTS = ["mousemove", "mousedown", "keydown", "touchstart", "scroll"] as const;

export function SessionTimeoutModal() {
  const { status } = useSession();
  const [showWarning, setShowWarning] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState(
    Math.floor(SESSION_CONFIG.warningBeforeTimeoutMs / 1000)
  );
  const idleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const resetIdleTimer = useCallback(() => {
    setShowWarning(false);
    if (countdownRef.current) clearInterval(countdownRef.current);
    if (idleTimerRef.current) clearTimeout(idleTimerRef.current);

    if (status !== "authenticated") return;

    const warningAt = SESSION_CONFIG.idleTimeoutMs - SESSION_CONFIG.warningBeforeTimeoutMs;
    idleTimerRef.current = setTimeout(() => {
      setShowWarning(true);
      setSecondsLeft(Math.floor(SESSION_CONFIG.warningBeforeTimeoutMs / 1000));
      countdownRef.current = setInterval(() => {
        setSecondsLeft((s) => {
          if (s <= 1) {
            clearInterval(countdownRef.current!);
            signOut({ callbackUrl: "/login" });
            return 0;
          }
          return s - 1;
        });
      }, 1000);
    }, warningAt);
  }, [status]);

  useEffect(() => {
    if (status !== "authenticated") return;

    resetIdleTimer();
    EVENTS.forEach((event) => window.addEventListener(event, resetIdleTimer, { passive: true }));

    return () => {
      EVENTS.forEach((event) => window.removeEventListener(event, resetIdleTimer));
      if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
      if (countdownRef.current) clearInterval(countdownRef.current);
    };
  }, [status, resetIdleTimer]);

  if (!showWarning) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70"
      role="dialog"
      aria-modal="true"
      aria-label="Session timeout warning"
    >
      <div className="w-full max-w-sm rounded-lg border bg-card p-6 shadow-xl text-center">
        <ShieldAlert className="mx-auto h-10 w-10 text-amber-500 mb-4" />
        <h2 className="text-lg font-semibold mb-2">Session Expiring Soon</h2>
        <p className="text-sm text-muted-foreground mb-4">
          You will be signed out in{" "}
          <span className="font-bold text-amber-500">{secondsLeft}</span> second
          {secondsLeft !== 1 ? "s" : ""} due to inactivity.
        </p>
        <div className="flex gap-3 justify-center">
          <button
            onClick={resetIdleTimer}
            className="flex-1 rounded-md bg-teal-500 px-4 py-2 text-sm font-medium text-white hover:bg-teal-600 transition-colors"
          >
            Stay signed in
          </button>
          <button
            onClick={() => signOut({ callbackUrl: "/login" })}
            className="flex-1 rounded-md border px-4 py-2 text-sm font-medium hover:bg-muted transition-colors"
          >
            Sign out
          </button>
        </div>
      </div>
    </div>
  );
}
