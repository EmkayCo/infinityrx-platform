"use client";

import React from "react";
import { cn } from "@shared/lib/format";

interface EmptyStateAction {
  label: string;
  onClick: () => void;
}

interface EmptyStateProps {
  title: string;
  description?: string;
  icon?: React.ReactNode;
  /** Either a ReactNode or a shorthand {label, onClick} object */
  action?: React.ReactNode | EmptyStateAction;
  className?: string;
}

function isActionObject(
  action: React.ReactNode | EmptyStateAction
): action is EmptyStateAction {
  return (
    typeof action === "object" &&
    action !== null &&
    !React.isValidElement(action) &&
    "label" in action &&
    "onClick" in action
  );
}

export function EmptyState({
  title,
  description,
  icon,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center py-16 px-8 text-center",
        className
      )}
    >
      {icon && (
        <div className="text-muted-foreground mb-4" aria-hidden="true">
          {icon}
        </div>
      )}
      <h3 className="font-medium text-base mb-2">{title}</h3>
      {description && (
        <p className="text-muted-foreground text-sm max-w-md mb-6">{description}</p>
      )}
      {action && isActionObject(action) ? (
        <button
          onClick={action.onClick}
          className="mt-1 rounded-md bg-teal-500 px-4 py-2 text-sm font-medium text-white hover:bg-teal-600 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500"
        >
          {action.label}
        </button>
      ) : (
        action
      )}
    </div>
  );
}
