"use client";

import { useState } from "react";
import { Search, LogOut, User, Settings, Menu } from "lucide-react";
import Link from "next/link";
import { cn } from "@shared/lib/format";
import { ThemeToggle } from "@shared/components/theme-toggle";
import { NotificationCenter } from "@shared/components/notification-center";
import { useAuth } from "@shared/hooks/use-auth";
import { Breadcrumbs } from "./breadcrumbs";
import { ThemeToggleButton } from "./theme-toggle-button";

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
        "flex h-14 items-center gap-3 border-b border-ifx-gray-100 bg-white px-4 shrink-0",
        className,
      )}
    >
      {/* Mobile menu toggle */}
      <button
        onClick={onMenuToggle}
        className="lg:hidden text-ifx-gray-400 hover:text-ifx-gray-700"
        aria-label="Toggle navigation menu"
      >
        <Menu className="h-5 w-5" />
      </button>

      {/* Breadcrumbs — left */}
      <div className="hidden md:flex items-center min-w-0 flex-shrink">
        <Breadcrumbs />
      </div>

      {/* Global search — center */}
      <div className="flex flex-1 justify-center px-2">
        <button
          onClick={onCommandPaletteOpen}
          className={cn(
            "flex w-full max-w-md items-center gap-2 rounded-md border border-ifx-gray-100 px-3 py-1.5",
            "bg-ifx-gray-50 text-sm text-ifx-gray-400 hover:bg-white hover:border-ifx-gray-200 transition-colors",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ifx-blue/40",
          )}
          aria-label="Open command palette (Cmd+K)"
        >
          <Search className="h-4 w-4 shrink-0" />
          <span className="hidden sm:inline flex-1 text-left">
            Search claims, pharmacies, prescribers...
          </span>
          <span className="sm:hidden flex-1 text-left">Search</span>
          <kbd className="ml-auto hidden sm:inline-flex items-center gap-0.5 rounded border border-ifx-gray-200 bg-white px-1.5 py-0.5 font-mono text-[11px] text-ifx-gray-400">
            <span>⌘</span>K
          </kbd>
        </button>
      </div>

      {/* Right side actions */}
      <div className="flex items-center gap-1">
        <ThemeToggleButton />
        <NotificationCenter />

        <div className="relative">
          <button
            onClick={() => setUserMenuOpen((o) => !o)}
            className={cn(
              "flex items-center gap-2 rounded-md px-2 py-1.5 text-sm",
              "hover:bg-ifx-gray-50 transition-colors",
              userMenuOpen && "bg-ifx-gray-50",
            )}
            aria-label="User menu"
            aria-expanded={userMenuOpen}
          >
            <div
              className="ifx-on-dark flex h-7 w-7 items-center justify-center rounded-full bg-ifx-navy text-xs font-bold text-white"
              aria-hidden="true"
            >
              {user?.name?.charAt(0)?.toUpperCase() ?? "?"}
            </div>
            <span className="hidden md:inline max-w-[120px] truncate font-medium text-ifx-gray-700">
              {user?.name}
            </span>
          </button>

          {userMenuOpen && (
            <>
              <div
                className="fixed inset-0 z-40"
                onClick={() => setUserMenuOpen(false)}
                aria-hidden="true"
              />
              <div className="absolute right-0 top-11 z-50 w-56 rounded-lg border border-ifx-gray-100 bg-white shadow-lg overflow-hidden">
                <div className="border-b border-ifx-gray-100 px-4 py-3">
                  <p className="font-medium text-sm text-ifx-gray-900">{user?.name}</p>
                  <p className="text-xs text-ifx-gray-400">{user?.email}</p>
                  <p className="mt-0.5 text-xs text-ifx-blue font-medium capitalize">
                    {user?.role?.replace("_", " ")}
                  </p>
                </div>

                <div className="p-1">
                  <Link
                    href="/settings/profile"
                    onClick={() => setUserMenuOpen(false)}
                    className="flex items-center gap-2.5 rounded-md px-3 py-2 text-sm text-ifx-gray-700 hover:bg-ifx-lavender transition-colors"
                  >
                    <User className="h-4 w-4 text-ifx-gray-400" />
                    Profile
                  </Link>
                  <Link
                    href="/settings"
                    onClick={() => setUserMenuOpen(false)}
                    className="flex items-center gap-2.5 rounded-md px-3 py-2 text-sm text-ifx-gray-700 hover:bg-ifx-lavender transition-colors"
                  >
                    <Settings className="h-4 w-4 text-ifx-gray-400" />
                    Settings
                  </Link>

                  <div className="my-1 border-t border-ifx-gray-100" />

                  <div className="flex items-center gap-2.5 px-3 py-2">
                    <span className="text-sm text-ifx-gray-400">Theme</span>
                    <div className="ml-auto">
                      <ThemeToggle />
                    </div>
                  </div>

                  <div className="my-1 border-t border-ifx-gray-100" />

                  <button
                    onClick={() => {
                      setUserMenuOpen(false);
                      signOut({ callbackUrl: "/login" });
                    }}
                    className="flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-sm text-ifx-error hover:bg-ifx-error-light transition-colors"
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
