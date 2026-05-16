"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "./sidebar";
import { Topbar } from "./topbar";
import { SectionTabs } from "./section-tabs";
import { RightStrip, RIGHT_PANEL_CONTENT, type RightPanelId } from "./right-strip";
import { SlidingPanel } from "./sliding-panel";
import { SessionTimeoutModal } from "./session-timeout-modal";
import { DemoBanner } from "@shared/components/demo-banner";
import { ShortcutsOverlay } from "@shared/components/shortcuts-overlay";
import { CommandPalette, useCommandPalette } from "@shared/components/command-palette";
import { useGlobalKeyboardShortcuts, useKeyboardShortcut } from "@shared/hooks/use-keyboard-shortcuts";
import { searchEntities } from "./entity-search";

interface AppShellProps {
  isAuthenticated: boolean;
  children: React.ReactNode;
  /** Optional manifest-driven nav slot (Plan D SP-0 composition). */
  nav?: React.ReactNode;
}

export function AppShell({ isAuthenticated, children, nav: _nav }: AppShellProps) {
  const router = useRouter();
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [activePanel, setActivePanel] = useState<RightPanelId | null>(null);
  const { open: cmdPaletteOpen, setOpen: setCmdPaletteOpen } = useCommandPalette();

  useGlobalKeyboardShortcuts();

  useKeyboardShortcut({
    id: "shortcuts-overlay",
    label: "Show shortcuts overlay",
    keys: "?",
    handler: () => setShortcutsOpen(true),
    category: "Navigation",
  });

  useKeyboardShortcut({
    id: "goto-dashboard",
    label: "Go to Dashboard",
    keys: "g d",
    handler: () => router.push("/"),
    category: "Navigation",
  });
  useKeyboardShortcut({
    id: "goto-claims",
    label: "Go to Claims",
    keys: "g c",
    handler: () => router.push("/claims"),
    category: "Navigation",
  });
  useKeyboardShortcut({
    id: "goto-reclaimrx",
    label: "Go to ReclaimRx",
    keys: "g r",
    handler: () => router.push("/reclaimrx"),
    category: "Navigation",
  });
  useKeyboardShortcut({
    id: "goto-accounting",
    label: "Go to Accounting",
    keys: "g a",
    handler: () => router.push("/accounting/cycles"),
    category: "Navigation",
  });

  if (!isAuthenticated) {
    return <div className="min-h-screen">{children}</div>;
  }

  const handlePanelOpen = (id: RightPanelId) =>
    setActivePanel((current) => (current === id ? null : id));

  const panelContent = activePanel ? RIGHT_PANEL_CONTENT[activePanel] : null;

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <DemoBanner />

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar — desktop */}
        <Sidebar className="hidden lg:flex" />

        {/* Mobile sidebar overlay */}
        {mobileSidebarOpen && (
          <>
            <div
              className="fixed inset-0 z-40 bg-ifx-navy-dark/50 lg:hidden"
              onClick={() => setMobileSidebarOpen(false)}
              aria-hidden="true"
            />
            <div className="fixed inset-y-0 left-0 z-50 lg:hidden">
              <Sidebar className="flex h-full" />
            </div>
          </>
        )}

        {/* Main column: topbar + section-tabs + content */}
        <div className="flex flex-1 flex-col min-w-0 overflow-hidden">
          <Topbar
            onMenuToggle={() => setMobileSidebarOpen((o) => !o)}
            onCommandPaletteOpen={() => setCmdPaletteOpen(true)}
          />
          <SectionTabs />
          <main
            id="main-content"
            className="flex-1 overflow-y-auto bg-ifx-gray-50 p-6"
            tabIndex={-1}
          >
            {children}
          </main>
        </div>

        {/* Right action strip */}
        <RightStrip activePanel={activePanel} onOpenPanel={handlePanelOpen} />
      </div>

      {/* Sliding panel (portaled fixed element) */}
      {panelContent && (
        <SlidingPanel
          open={!!activePanel}
          onClose={() => setActivePanel(null)}
          title={panelContent.title}
        >
          <div className="flex flex-col items-center justify-center h-full text-center text-sm text-ifx-gray-400 py-12">
            <p>{panelContent.placeholder}</p>
          </div>
        </SlidingPanel>
      )}

      {/* Global overlays */}
      <SessionTimeoutModal />
      <ShortcutsOverlay open={shortcutsOpen} onClose={() => setShortcutsOpen(false)} />
      <CommandPalette
        open={cmdPaletteOpen}
        onOpenChange={setCmdPaletteOpen}
        onNavigate={(href) => router.push(href)}
        entitySearch={searchEntities}
      />
    </div>
  );
}
