"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ChevronLeft,
  ChevronRight,
  ChevronDown,
} from "lucide-react";
import { cn } from "@shared/lib/format";
import { useAuth } from "@shared/hooks/use-auth";
import { Permission } from "@shared/types/auth";
import { IfxLogo } from "@/components/ui/ifx-logo";
import { NAV_MODULES, type NavModule, findActiveModule } from "./nav-config";

const COLLAPSED_KEY = "ifx-sidebar-collapsed";
const EXPANDED_KEY = "ifx-sidebar-expanded-modules";

export function Sidebar({ className }: { className?: string }) {
  const pathname = usePathname();
  const { user, hasPermission } = useAuth();
  const [collapsed, setCollapsed] = useState(false);
  const [expandedModules, setExpandedModules] = useState<Record<string, boolean>>({});
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    const storedCollapsed = localStorage.getItem(COLLAPSED_KEY);
    if (storedCollapsed === "true") setCollapsed(true);
    const storedExpanded = localStorage.getItem(EXPANDED_KEY);
    if (storedExpanded) {
      try {
        setExpandedModules(JSON.parse(storedExpanded));
      } catch {
        // ignore
      }
    }
    setHydrated(true);
  }, []);

  // Auto-expand the module that contains the active path
  useEffect(() => {
    if (!hydrated) return;
    const active = findActiveModule(pathname);
    if (active?.children && !expandedModules[active.label]) {
      const next = { ...expandedModules, [active.label]: true };
      setExpandedModules(next);
      localStorage.setItem(EXPANDED_KEY, JSON.stringify(next));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname, hydrated]);

  function toggleCollapse() {
    setCollapsed((c) => {
      const next = !c;
      localStorage.setItem(COLLAPSED_KEY, String(next));
      return next;
    });
  }

  function toggleExpand(label: string) {
    setExpandedModules((prev) => {
      const next = { ...prev, [label]: !prev[label] };
      localStorage.setItem(EXPANDED_KEY, JSON.stringify(next));
      return next;
    });
  }

  function canSeeModule(mod: NavModule): boolean {
    if (!user) return true; // permissive during dev / before session loads
    if (mod.permission) return hasPermission(mod.permission);
    return true;
  }

  const activeModule = findActiveModule(pathname);

  return (
    <aside
      className={cn(
        "ifx-on-dark flex h-full flex-col bg-[var(--bg-sidebar)] transition-all duration-200",
        "dark:border-r dark:border-[var(--border-strong)]",
        collapsed ? "w-16" : "w-60",
        className,
      )}
      aria-label="Main navigation"
    >
      {/* Logo header */}
      <div className="flex h-20 items-center justify-center border-b border-white/10 px-4 shrink-0">
        <Link
          href="/"
          className="flex items-center justify-center"
          aria-label="InfinityRx Home"
        >
          <IfxLogo variant="white" size="sm" showWordmark={!collapsed} />
        </Link>
      </div>

      {/* Navigation list */}
      <nav className="flex-1 overflow-y-auto pt-8 pb-3" aria-label="Sidebar navigation">
        <div className="space-y-0.5 px-2">
          {NAV_MODULES.filter(canSeeModule).map((mod) => (
            <ModuleRow
              key={mod.label}
              module={mod}
              collapsed={collapsed}
              isActive={activeModule?.label === mod.label}
              isExpanded={!!expandedModules[mod.label]}
              onToggleExpand={() => toggleExpand(mod.label)}
              pathname={pathname}
              hasPermission={hasPermission}
              hasUser={!!user}
            />
          ))}
        </div>
      </nav>

      {/* Tenant label + collapse toggle */}
      <div className="border-t border-white/10 shrink-0">
        {!collapsed && (
          <div className="px-4 py-2 text-[10px] font-medium uppercase tracking-wider text-white/50">
            InfinityRx
          </div>
        )}
        <button
          onClick={toggleCollapse}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className={cn(
            "flex w-full items-center gap-2 px-4 py-3 text-white/70 transition-colors hover:bg-[var(--bg-sidebar-hover)] hover:text-white",
            collapsed && "justify-center px-0",
          )}
        >
          {collapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <>
              <ChevronLeft className="h-4 w-4" />
              <span className="text-xs">Minimize</span>
            </>
          )}
        </button>
      </div>
    </aside>
  );
}

interface ModuleRowProps {
  module: NavModule;
  collapsed: boolean;
  isActive: boolean;
  isExpanded: boolean;
  onToggleExpand: () => void;
  pathname: string;
  hasPermission: (p: Permission) => boolean;
  hasUser: boolean;
}

function ModuleRow({
  module: mod,
  collapsed,
  isActive,
  isExpanded,
  onToggleExpand,
  pathname,
  hasPermission,
  hasUser,
}: ModuleRowProps) {
  const Icon = mod.icon;
  const hasChildren = !!mod.children?.length;

  // Collapsed mode — icon only, navigate directly (click the icon)
  if (collapsed) {
    return (
      <Link
        href={mod.href}
        title={mod.label}
        aria-label={mod.label}
        className={cn(
          "relative flex items-center justify-center rounded-md py-2.5 transition-colors",
          isActive
            ? "bg-[var(--bg-sidebar-hover)] text-white"
            : "text-white/70 hover:bg-[var(--bg-sidebar-hover)] hover:text-white",
        )}
      >
        {isActive && (
          <span className="absolute left-0 top-1/2 h-6 w-[3px] -translate-y-1/2 rounded-r bg-ifx-primary" />
        )}
        <Icon className="h-5 w-5" />
      </Link>
    );
  }

  // Expanded + children — expandable row
  if (hasChildren) {
    return (
      <div>
        <button
          type="button"
          onClick={onToggleExpand}
          aria-expanded={isExpanded}
          className={cn(
            "relative flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors",
            isActive
              ? "bg-[var(--bg-sidebar-hover)] text-white"
              : "text-white/80 hover:bg-[var(--bg-sidebar-hover)] hover:text-white",
          )}
        >
          {isActive && (
            <span className="absolute left-0 top-1/2 h-6 w-[3px] -translate-y-1/2 rounded-r bg-ifx-primary" />
          )}
          <Icon className="h-4 w-4 shrink-0" />
          <span className="flex-1 text-left truncate">{mod.label}</span>
          <ChevronDown
            className={cn(
              "h-3.5 w-3.5 shrink-0 opacity-60 transition-transform",
              isExpanded ? "rotate-0" : "-rotate-90",
            )}
          />
        </button>

        {isExpanded && (
          <div className="mt-0.5 ml-4 space-y-0.5 border-l border-white/10 pl-3">
            {mod.children!.map((child) => {
              // Permission gate
              if (child.permission && hasUser && !hasPermission(child.permission)) {
                return null;
              }
              const active =
                pathname === child.href || pathname.startsWith(child.href + "/");
              return (
                <Link
                  key={child.href}
                  href={child.href}
                  className={cn(
                    "block rounded-md px-3 py-1.5 text-[13px] transition-colors",
                    active
                      ? "bg-[var(--bg-sidebar-hover)] font-semibold text-white"
                      : "text-white/60 hover:bg-[var(--bg-sidebar-hover)] hover:text-white",
                  )}
                  aria-current={active ? "page" : undefined}
                >
                  {child.label}
                </Link>
              );
            })}
          </div>
        )}
      </div>
    );
  }

  // Leaf module (no children) — direct link
  return (
    <Link
      href={mod.href}
      className={cn(
        "relative flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors",
        isActive
          ? "bg-[var(--bg-sidebar-hover)] text-white"
          : "text-white/80 hover:bg-[var(--bg-sidebar-hover)] hover:text-white",
      )}
      aria-current={isActive ? "page" : undefined}
    >
      {isActive && (
        <span className="absolute left-0 top-1/2 h-6 w-[3px] -translate-y-1/2 rounded-r bg-ifx-primary" />
      )}
      <Icon className="h-4 w-4 shrink-0" />
      <span className="flex-1 truncate">{mod.label}</span>
    </Link>
  );
}
