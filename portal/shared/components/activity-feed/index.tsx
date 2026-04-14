"use client";

import React from "react";
import { cn, formatRelative } from "@shared/lib/format";
import type { ActivityEvent } from "@shared/types/common";
import type { Severity } from "@shared/types/common";

const severityDot: Record<Severity, string> = {
  critical: "bg-red-500",
  high: "bg-red-400",
  medium: "bg-yellow-400",
  low: "bg-blue-400",
  info: "bg-green-400",
};

interface ActivityFeedProps {
  events: ActivityEvent[];
  isLoading?: boolean;
  className?: string;
  onEventClick?: (event: ActivityEvent) => void;
}

export function ActivityFeed({
  events,
  isLoading,
  className,
  onEventClick,
}: ActivityFeedProps) {
  if (isLoading) {
    return (
      <div className={cn("space-y-3", className)}>
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="flex gap-3 animate-pulse">
            <div className="w-2 h-2 rounded-full bg-slate-700 mt-2 flex-shrink-0" />
            <div className="flex-1 space-y-1">
              <div className="h-3 bg-slate-700 rounded w-4/5" />
              <div className="h-3 bg-slate-700/50 rounded w-2/5" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (events.length === 0) {
    return (
      <p className={cn("text-sm text-slate-500 text-center py-6", className)}>
        No recent activity
      </p>
    );
  }

  return (
    <div className={cn("space-y-1", className)}>
      {events.map((event) => (
        <div
          key={event.id}
          onClick={() => onEventClick?.(event)}
          className={cn(
            "flex gap-3 px-3 py-2.5 rounded-lg hover:bg-navy-700/30 transition-colors group",
            onEventClick && "cursor-pointer"
          )}
        >
          <span
            className={cn(
              "w-2 h-2 rounded-full flex-shrink-0 mt-1.5",
              severityDot[event.severity]
            )}
            aria-hidden="true"
          />
          <div className="flex-1 min-w-0">
            <p className="text-sm text-slate-200 leading-snug truncate">
              <span className="font-medium">{event.user_name}</span>{" "}
              {event.description}
            </p>
            <p className="text-xs text-slate-500 mt-0.5">
              {formatRelative(event.occurred_at)} · {event.module}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}
