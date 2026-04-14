"use client";

import { useState, useCallback } from "react";
import { Bell, Check, CheckCheck, X } from "lucide-react";
import { cn, formatRelative } from "@shared/lib/format";
import { useSSE } from "@shared/hooks/use-sse";
import type { Notification } from "@shared/types/common";
import { API_URLS } from "@shared/lib/constants";

const SEVERITY_COLORS = {
  critical: "text-red-500",
  high: "text-red-400",
  medium: "text-amber-400",
  low: "text-blue-400",
  info: "text-slate-400",
};

const SEVERITY_DOTS = {
  critical: "bg-red-500",
  high: "bg-red-400",
  medium: "bg-amber-400",
  low: "bg-blue-400",
  info: "bg-slate-400",
};

interface NotificationCenterProps {
  getToken?: () => string | null | undefined;
}

export function NotificationCenter({ getToken }: NotificationCenterProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [filter, setFilter] = useState<string>("all");

  // Real-time SSE stream
  useSSE<Notification>(
    {
      url: `${API_URLS.corePlatform}/notifications/stream`,
      getToken,
    },
    useCallback((event: import("@shared/hooks/use-sse").SSEEvent<Notification>) => {
      if (event.type === "notification") {
        setNotifications((prev) => [event.data, ...prev.slice(0, 99)]);
      }
    }, [])
  );

  const unreadCount = notifications.filter((n) => !n.read).length;

  function markRead(id: string) {
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, read: true } : n))
    );
  }

  function markAllRead() {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  }

  function dismiss(id: string) {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }

  const filtered =
    filter === "all" ? notifications : notifications.filter((n) => n.type === filter);

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen((o) => !o)}
        aria-label={`Notifications${unreadCount > 0 ? `, ${unreadCount} unread` : ""}`}
        aria-expanded={isOpen}
        className="relative flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
      >
        <Bell className="h-5 w-5" />
        {unreadCount > 0 && (
          <span
            className="absolute -right-0.5 -top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-xs font-bold text-white"
            aria-hidden="true"
          >
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => setIsOpen(false)}
            aria-hidden="true"
          />
          <div
            className={cn(
              "absolute right-0 top-11 z-50 w-96 max-w-[calc(100vw-1rem)]",
              "rounded-lg border bg-popover shadow-lg"
            )}
            role="dialog"
            aria-label="Notifications"
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b px-4 py-3">
              <h2 className="font-semibold text-sm">Notifications</h2>
              <div className="flex items-center gap-2">
                {unreadCount > 0 && (
                  <button
                    onClick={markAllRead}
                    className="flex items-center gap-1 text-xs text-teal-600 dark:text-teal-400 hover:underline"
                    aria-label="Mark all notifications as read"
                  >
                    <CheckCheck className="h-3.5 w-3.5" />
                    Mark all read
                  </button>
                )}
                <button
                  onClick={() => setIsOpen(false)}
                  aria-label="Close notifications"
                  className="text-muted-foreground hover:text-foreground"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>

            {/* Body */}
            <div className="max-h-80 overflow-y-auto">
              {filtered.length === 0 ? (
                <div className="flex flex-col items-center justify-center gap-2 py-8 text-sm text-muted-foreground">
                  <Bell className="h-8 w-8 opacity-30" />
                  <p>No notifications</p>
                </div>
              ) : (
                filtered.map((notification) => (
                  <div
                    key={notification.id}
                    className={cn(
                      "group relative flex gap-3 px-4 py-3 border-b last:border-0 transition-colors",
                      !notification.read && "bg-teal-50/30 dark:bg-teal-950/20"
                    )}
                  >
                    <div className="mt-1 shrink-0">
                      <span
                        className={cn(
                          "block h-2 w-2 rounded-full",
                          SEVERITY_DOTS[notification.severity]
                        )}
                        aria-hidden="true"
                      />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p
                        className={cn(
                          "text-sm font-medium leading-snug",
                          SEVERITY_COLORS[notification.severity]
                        )}
                      >
                        {notification.title}
                      </p>
                      <p className="mt-0.5 text-xs text-muted-foreground line-clamp-2">
                        {notification.message}
                      </p>
                      <p className="mt-1 text-xs text-muted-foreground/70">
                        {formatRelative(notification.created_at)}
                      </p>
                    </div>
                    <div className="flex shrink-0 flex-col gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      {!notification.read && (
                        <button
                          onClick={() => markRead(notification.id)}
                          aria-label="Mark as read"
                          className="text-muted-foreground hover:text-foreground"
                        >
                          <Check className="h-3.5 w-3.5" />
                        </button>
                      )}
                      <button
                        onClick={() => dismiss(notification.id)}
                        aria-label="Dismiss notification"
                        className="text-muted-foreground hover:text-foreground"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
