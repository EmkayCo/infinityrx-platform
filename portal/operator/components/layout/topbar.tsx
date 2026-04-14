"use client";

import { useState } from "react";
import { Search, LogOut, User, Settings, Menu } from "lucide-react";
import Link from "next/link";
import { cn } from "@shared/lib/format";
import { ThemeToggle } from "@shared/components/theme-toggle";
import { NotificationCenter } from "@shared/components/notification-center";
import { useAuth } from "@shared/hooks/use-auth";

interface TopbarProps {
  onMenuToggle?: () => void;
  onCommandPaletteOpen?: () => void;
  className?: string;
}

export function Topbar({ onMenuToggle, onCommandPaletteOpen, className }: TopbarProps) {
  const { user, signOut } = useAuth();
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  return (
    <header
      className={cn(
        "flex h-14 items-center gap-3 border-b bg-card px-4 shrink-0",
        className
      )}
    >
      {/* Mobile menu toggle */}
      <button
        onClick={onMenuToggle}
        className="lg:hidden text-muted-foreground hover:text-foreground"
        aria-label="Toggle navigation menu"
      >
        <Menu className="h-5 w-5" />
      </button>

      {/* Command palette trigger */}
      <button
        onClick={onCommandPaletteOpen}
        className={cn(
          "flex flex-1 max-w-xs items-center gap-2 rounded-md border px-3 py-1.5",
          "bg-muted/50 text-sm text-muted-foreground hover:bg-muted transition-colors",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500"
        )}
        aria-label="Open command palette (Cmd+K)"
      >
        <Search className="h-4 w-4 shrink-0" />
        <span className="hidden sm:inline">Search actions, records, pages...</span>
        <kbd className="ml-auto hidden sm:inline-flex items-center gap-0.5 rounded border px-1.5 py-0.5 text-xs font-mono text-muted-foreground">
          <span>⌘</span>K
        </kbd>
      </button>

      <div className="flex-1" />

      {/* Right side actions */}
      <div className="flex items-center gap-2">
        {/* Notifications */}
        <NotificationCenter />

        {/* User menu */}
        <div className="relative">
          <button
            onClick={() => setUserMenuOpen((o) => !o)}
            className={cn(
              "flex items-center gap-2 rounded-md px-2 py-1.5 text-sm",
              "hover:bg-accent transition-colors",
              userMenuOpen && "bg-accent"
            )}
            aria-label="User menu"
            aria-expanded={userMenuOpen}
          >
            <div
              className="flex h-7 w-7 items-center justify-center rounded-full bg-teal-500 text-xs font-bold text-white"
              aria-hidden="true"
            >
              {user?.name?.charAt(0)?.toUpperCase() ?? "?"}
            </div>
            <span className="hidden md:inline max-w-24 truncate font-medium">{user?.name}</span>
          </button>

          {userMenuOpen && (
            <>
              <div
                className="fixed inset-0 z-40"
                onClick={() => setUserMenuOpen(false)}
                aria-hidden="true"
              />
              <div className="absolute right-0 top-11 z-50 w-56 rounded-lg border bg-popover shadow-lg overflow-hidden">
                <div className="border-b px-4 py-3">
                  <p className="font-medium text-sm">{user?.name}</p>
                  <p className="text-xs text-muted-foreground">{user?.email}</p>
                  <p className="mt-0.5 text-xs text-teal-600 dark:text-teal-400 font-medium capitalize">
                    {user?.role?.replace("_", " ")}
                  </p>
                </div>

                <div className="p-1">
                  <Link
                    href="/settings/profile"
                    onClick={() => setUserMenuOpen(false)}
                    className="flex items-center gap-2.5 rounded-md px-3 py-2 text-sm hover:bg-accent transition-colors"
                  >
                    <User className="h-4 w-4 text-muted-foreground" />
                    Profile
                  </Link>
                  <Link
                    href="/settings"
                    onClick={() => setUserMenuOpen(false)}
                    className="flex items-center gap-2.5 rounded-md px-3 py-2 text-sm hover:bg-accent transition-colors"
                  >
                    <Settings className="h-4 w-4 text-muted-foreground" />
                    Settings
                  </Link>

                  <div className="my-1 border-t" />

                  <div className="flex items-center gap-2.5 px-3 py-2">
                    <span className="text-sm text-muted-foreground">Theme</span>
                    <div className="ml-auto">
                      <ThemeToggle />
                    </div>
                  </div>

                  <div className="my-1 border-t" />

                  <button
                    onClick={() => {
                      setUserMenuOpen(false);
                      signOut({ callbackUrl: "/login" });
                    }}
                    className="flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-sm text-destructive hover:bg-destructive/10 transition-colors"
                  >
                    <LogOut className="h-4 w-4" />
                    Sign out
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
