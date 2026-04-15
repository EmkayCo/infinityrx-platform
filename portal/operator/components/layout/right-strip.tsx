"use client";

import { Bot, Star, Bell, HelpCircle, type LucideIcon } from "lucide-react";
import { cn } from "@shared/lib/format";

export type RightPanelId = "assistant" | "tasks" | "notifications" | "support";

interface RightStripProps {
  activePanel: RightPanelId | null;
  onOpenPanel: (id: RightPanelId) => void;
  notificationCount?: number;
  className?: string;
}

interface StripButton {
  id: RightPanelId;
  label: string;
  icon: LucideIcon;
}

const BUTTONS: StripButton[] = [
  { id: "assistant", label: "Assistant", icon: Bot },
  { id: "tasks", label: "Tasks", icon: Star },
  { id: "notifications", label: "Notifications", icon: Bell },
  { id: "support", label: "Support", icon: HelpCircle },
];

/**
 * 48px vertical action strip on the far right edge of the app shell.
 * Each icon opens a sliding panel with context-specific content.
 */
export function RightStrip({
  activePanel,
  onOpenPanel,
  notificationCount = 0,
  className,
}: RightStripProps) {
  return (
    <aside
      className={cn(
        "hidden md:flex w-12 flex-col items-center gap-1 border-l border-ifx-gray-100 bg-ifx-gray-50 py-3 shrink-0",
        className,
      )}
      aria-label="Quick actions"
    >
      {BUTTONS.map((btn) => {
        const Icon = btn.icon;
        const isActive = activePanel === btn.id;
        const showBadge = btn.id === "notifications" && notificationCount > 0;
        return (
          <button
            key={btn.id}
            type="button"
            onClick={() => onOpenPanel(btn.id)}
            title={btn.label}
            aria-label={btn.label}
            aria-pressed={isActive}
            className={cn(
              "relative flex h-10 w-10 items-center justify-center rounded-md transition-colors",
              isActive
                ? "bg-ifx-blue/10 text-ifx-blue"
                : "text-ifx-gray-400 hover:bg-ifx-lavender hover:text-ifx-navy",
            )}
          >
            <Icon className="h-5 w-5" />
            {showBadge && (
              <span
                className="absolute right-1.5 top-1.5 flex h-2 w-2 rounded-full bg-ifx-error"
                aria-hidden="true"
              />
            )}
          </button>
        );
      })}
    </aside>
  );
}

export const RIGHT_PANEL_CONTENT: Record<
  RightPanelId,
  { title: string; placeholder: string }
> = {
  assistant: {
    title: "IFX Assistant",
    placeholder: "Ask questions about claims, pharmacies, or programs. Coming in Phase 1D.",
  },
  tasks: {
    title: "Tasks",
    placeholder: "Context-sensitive action links for the current page. Coming in Phase 1D.",
  },
  notifications: {
    title: "Notifications",
    placeholder: "No new notifications. System alerts and task updates will appear here.",
  },
  support: {
    title: "Help & Documentation",
    placeholder: "Search documentation, user guides, and release notes. Coming in Phase 1D.",
  },
};
