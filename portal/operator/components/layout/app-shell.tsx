"use client";

import { useState } from "react";
import { Sidebar } from "./sidebar";
import { Topbar } from "./topbar";
import { SessionTimeoutModal } from "./session-timeout-modal";
import { DemoBanner } from "@shared/components/demo-banner";
import { ShortcutsOverlay } from "@shared/components/shortcuts-overlay";
import { CommandPalette, useCommandPalette } from "@shared/components/command-palette";
import { useGlobalKeyboardShortcuts, useKeyboardShortcut } from "@shared/hooks/use-keyboard-shortcuts";
import { useRouter } from "next/navigation";

interface AppShellProps {
  isAuthenticated: boolean;
  children: React.ReactNode;
}

export function AppShell({ isAuthenticated, children }: AppShellProps) {
  const router = useRouter();
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const { open: cmdPaletteOpen, setOpen: setCmdPaletteOpen } = useCommandPalette();

  // Mount global keyboard shortcuts
  useGlobalKeyboardShortcuts();

  // Register app-level shortcuts
  useKeyboardShortcut({
    id: "shortcuts-overlay",
    label: "Show shortcuts overlay",
    keys: "?",
    handler: () => setShortcutsOpen(true),
    category: "Navigation",
  });

  useKeyboardShortcut({ id: "goto-dashboard", label: "Go to Dashboard", keys: "g d", handler: () => router.push("/"), category: "Navigation" });
  useKeyboardShortcut({ id: "goto-billing", label: "Go to Billing", keys: "g b", handler: () => router.push("/billing"), category: "Navigation" });
  useKeyboardShortcut({ id: "goto-reclaimrx", label: "Go to ReclaimRx", keys: "g r", handler: () => router.push("/reclaimrx"), category: "Navigation" });
  useKeyboardShortcut({ id: "goto-payments", label: "Go to Payments", keys: "g p", handler: () => router.push("/payments"), category: "Navigation" });

  if (!isAuthenticated) {
    return <div className="min-h-screen">{children}</div>;
  }

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      {/* Demo mode banner — renders only when NEXT_PUBLIC_USE_MOCK_DATA=true */}
      <DemoBanner />

      <div className="flex flex-1 overflow-hidden">
      {/* Sidebar — desktop */}
      <Sidebar className="hidden lg:flex flex-col" />

      {/* Mobile sidebar overlay */}
      {mobileSidebarOpen && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/50 lg:hidden"
            onClick={() => setMobileSidebarOpen(false)}
            aria-hidden="true"
          />
          <div className="fixed inset-y-0 left-0 z-50 lg:hidden">
            <Sidebar className="flex flex-col h-full" />
          </div>
        </>
      )}

      {/* Main content area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <Topbar
          onMenuToggle={() => setMobileSidebarOpen((o) => !o)}
          onCommandPaletteOpen={() => setCmdPaletteOpen(true)}
        />
        <main
          id="main-content"
          className="flex-1 overflow-y-auto bg-[var(--ifx-bg)] p-6"
          tabIndex={-1}
        >
          {children}
        </main>
      </div>

      {/* Global overlays */}
      <SessionTimeoutModal />
      <ShortcutsOverlay open={shortcutsOpen} onClose={() => setShortcutsOpen(false)} />
      <CommandPalette
        open={cmdPaletteOpen}
        onOpenChange={setCmdPaletteOpen}
        onNavigate={(href) => router.push(href)}
      />
      </div>
    </div>
  );
}
