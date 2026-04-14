"use client";

import { useEffect, useState } from "react";
import { Moon, Sun, Monitor } from "lucide-react";
import { cn } from "@shared/lib/format";

type Theme = "light" | "dark" | "system";

function applyTheme(theme: Theme) {
  const root = document.documentElement;
  if (theme === "system") {
    const systemDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    root.classList.toggle("dark", systemDark);
  } else {
    root.classList.toggle("dark", theme === "dark");
  }
}

export function ThemeToggle({ className }: { className?: string }) {
  const [theme, setTheme] = useState<Theme>("system");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const stored = localStorage.getItem("ifx-theme") as Theme | null;
    const initial = stored ?? "system";
    setTheme(initial);
    applyTheme(initial);

    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const listener = () => {
      if (theme === "system") applyTheme("system");
    };
    mq.addEventListener("change", listener);
    return () => mq.removeEventListener("change", listener);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function setAndPersist(next: Theme) {
    setTheme(next);
    localStorage.setItem("ifx-theme", next);
    applyTheme(next);
  }

  if (!mounted) return null;

  const options: { value: Theme; Icon: typeof Sun; label: string }[] = [
    { value: "light", Icon: Sun, label: "Light" },
    { value: "dark", Icon: Moon, label: "Dark" },
    { value: "system", Icon: Monitor, label: "System" },
  ];

  return (
    <div
      className={cn(
        "flex items-center gap-1 rounded-lg border border-[var(--ifx-border)] bg-[var(--ifx-surface)] p-1",
        className
      )}
      role="group"
      aria-label="Color theme"
    >
      {options.map(({ value, Icon, label }) => (
        <button
          key={value}
          onClick={() => setAndPersist(value)}
          aria-label={label}
          aria-pressed={theme === value}
          className={cn(
            "flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors",
            theme === value
              ? "bg-teal-500 text-white"
              : "text-[var(--ifx-text-secondary)] hover:bg-[var(--ifx-bg)] hover:text-[var(--ifx-text-primary)]"
          )}
        >
          <Icon className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">{label}</span>
        </button>
      ))}
    </div>
  );
}

/** Initialize theme from localStorage before React hydrates (prevents flash) */
export const themeInitScript = `
(function() {
  try {
    var t = localStorage.getItem('ifx-theme');
    var dark = t === 'dark' || (!t || t === 'system') && window.matchMedia('(prefers-color-scheme: dark)').matches;
    if (dark) document.documentElement.classList.add('dark');
  } catch(e) {}
})();
`;
