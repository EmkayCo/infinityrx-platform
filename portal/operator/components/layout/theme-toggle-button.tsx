"use client";

import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";
import { cn } from "@shared/lib/format";

type Theme = "light" | "dark";

function applyTheme(theme: Theme) {
  document.documentElement.classList.toggle("dark", theme === "dark");
}

function readInitialTheme(): Theme {
  if (typeof window === "undefined") return "light";
  const stored = localStorage.getItem("ifx-theme");
  if (stored === "dark") return "dark";
  if (stored === "light") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/**
 * Compact icon-only theme toggle for the top bar.
 * Shows a sun in dark mode (click → light), a moon in light mode (click → dark).
 * Persists to localStorage under `ifx-theme`.
 */
export function ThemeToggleButton({ className }: { className?: string }) {
  const [theme, setTheme] = useState<Theme>("light");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const initial = readInitialTheme();
    setTheme(initial);
    applyTheme(initial);

    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => {
      if (!localStorage.getItem("ifx-theme")) {
        const next = mq.matches ? "dark" : "light";
        setTheme(next);
        applyTheme(next);
      }
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  function toggle() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setTheme(next);
    localStorage.setItem("ifx-theme", next);
    applyTheme(next);
  }

  if (!mounted) {
    return (
      <button
        type="button"
        aria-label="Toggle theme"
        className={cn(
          "flex h-9 w-9 items-center justify-center rounded-md text-ifx-gray-400",
          className,
        )}
        disabled
      >
        <Moon className="h-4 w-4" />
      </button>
    );
  }

  const Icon = theme === "dark" ? Sun : Moon;
  const label = theme === "dark" ? "Switch to light mode" : "Switch to dark mode";

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={label}
      title={label}
      className={cn(
        "flex h-9 w-9 items-center justify-center rounded-md text-ifx-gray-500",
        "hover:bg-ifx-gray-100 hover:text-ifx-gray-900 transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ifx-primary",
        className,
      )}
    >
      <Icon className="h-4 w-4" />
    </button>
  );
}
