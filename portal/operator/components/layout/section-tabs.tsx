"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@shared/lib/format";
import { useAuth } from "@shared/hooks/use-auth";
import { findActiveModule, findActiveLeaf } from "./nav-config";

/**
 * Horizontal tab row below the topbar.
 * Mirrors the active sidebar module's children.
 * Does not render for modules without children (e.g., Dashboard).
 */
export function SectionTabs({ className }: { className?: string }) {
  const pathname = usePathname();
  const { user, hasPermission } = useAuth();
  const activeModule = findActiveModule(pathname);

  if (!activeModule || !activeModule.children || activeModule.children.length === 0) {
    return null;
  }

  const activeLeaf = findActiveLeaf(pathname, activeModule);

  const visibleChildren = activeModule.children.filter((child) => {
    if (!child.permission) return true;
    if (!user) return true;
    return hasPermission(child.permission);
  });

  return (
    <div
      className={cn(
        "flex h-11 items-center gap-1 overflow-x-auto border-b border-ifx-gray-100 bg-white px-4 shrink-0",
        "scrollbar-none",
        className,
      )}
      role="tablist"
      aria-label={`${activeModule.label} sections`}
    >
      {visibleChildren.map((child) => {
        const isActive = activeLeaf?.href === child.href;
        return (
          <Link
            key={child.href}
            href={child.href}
            role="tab"
            aria-selected={isActive}
            className={cn(
              "relative inline-flex items-center whitespace-nowrap px-3 py-2 text-sm transition-colors",
              "hover:text-ifx-gray-900",
              isActive
                ? "font-semibold text-ifx-gray-900"
                : "font-medium text-ifx-gray-400",
            )}
          >
            {child.label}
            {isActive && (
              <span
                className="absolute inset-x-3 bottom-0 h-0.5 rounded-t bg-ifx-blue"
                aria-hidden="true"
              />
            )}
          </Link>
        );
      })}
    </div>
  );
}
