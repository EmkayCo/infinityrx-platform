"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Receipt,
  Banknote,
  ShieldAlert,
  FileBarChart,
  Building2,
  Stethoscope,
  Pill,
  Users,
  ArrowLeftRight,
  FileHeart,
  BarChart3,
  UserCog,
  Building,
  Settings,
  ScrollText,
  Activity,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  Lock,
} from "lucide-react";
import { cn } from "@shared/lib/format";
import { useAuth } from "@shared/hooks/use-auth";
import { Permission, Role } from "@shared/types/auth";

interface NavLeaf {
  label: string;
  href: string;
}

interface NavItem {
  label: string;
  href: string;
  icon: React.ElementType;
  permission?: Permission;
  badge?: string;
  comingSoon?: boolean;
  children?: NavLeaf[];
}

interface NavSection {
  label?: string;
  items: NavItem[];
}

const NAV_SECTIONS: NavSection[] = [
  {
    label: "Main",
    items: [
      { label: "Dashboard", href: "/", icon: LayoutDashboard, permission: Permission.DashboardView },
    ],
  },
  {
    label: "Operations",
    items: [
      {
        label: "Billing",
        href: "/billing",
        icon: Receipt,
        permission: Permission.BillingView,
        children: [
          { label: "Billing Cycles", href: "/billing" },
          { label: "New Cycle", href: "/billing/cycles/new" },
          { label: "Claims Review", href: "/billing/claims" },
          { label: "Invoices", href: "/billing/invoices" },
        ],
      },
      {
        label: "Payments",
        href: "/payments",
        icon: Banknote,
        permission: Permission.PaymentsView,
        children: [
          { label: "Payment Batches", href: "/payments" },
          { label: "New Batch", href: "/payments/batches/new" },
          { label: "NACHA Files", href: "/payments/nacha" },
        ],
      },
      {
        label: "ReclaimRx",
        href: "/reclaimrx",
        icon: ShieldAlert,
        permission: Permission.ReclaimRxView,
        children: [
          { label: "FWA Flags", href: "/reclaimrx" },
          { label: "Investigations", href: "/reclaimrx/investigations" },
          { label: "Recovery Tracking", href: "/reclaimrx/recovery" },
        ],
      },
    ],
  },
  {
    label: "Reporting",
    items: [
      {
        label: "Reports",
        href: "/reporting",
        icon: FileBarChart,
        permission: Permission.ReportingView,
        children: [
          { label: "Report Library", href: "/reporting" },
          { label: "Report Builder", href: "/reporting/builder" },
          { label: "Scheduled Reports", href: "/reporting/scheduled" },
        ],
      },
    ],
  },
  {
    label: "Directories",
    items: [
      { label: "Pharmacies", href: "/directories/pharmacies", icon: Building2, permission: Permission.DirectoriesView },
      { label: "Prescribers", href: "/directories/prescribers", icon: Stethoscope, permission: Permission.DirectoriesView },
      { label: "Drugs", href: "/directories/drugs", icon: Pill, permission: Permission.DirectoriesView },
      { label: "Members", href: "/directories/members", icon: Users, permission: Permission.DirectoriesView },
    ],
  },
  {
    label: "EDI & Claims",
    items: [
      {
        label: "EDI Operations",
        href: "/edi",
        icon: ArrowLeftRight,
        permission: Permission.EDIView,
        children: [
          { label: "Trading Partners", href: "/edi/partners" },
          { label: "Transaction Monitor", href: "/edi/monitor" },
          { label: "Certificates", href: "/edi/certs" },
        ],
      },
      {
        label: "Medical Claims",
        href: "/medical-claims",
        icon: FileHeart,
        permission: Permission.DirectoriesView,
        children: [
          { label: "Claims Browser", href: "/medical-claims" },
          { label: "340B Summary", href: "/medical-claims/340b" },
          { label: "Unified Drug Spend", href: "/medical-claims/unified-spend" },
          { label: "HCPCS Crosswalk", href: "/medical-claims/crosswalk" },
          { label: "Site of Care", href: "/medical-claims/site-of-care" },
        ],
      },
    ],
  },
  {
    label: "Intelligence",
    items: [
      {
        label: "Analytics",
        href: "/analytics",
        icon: BarChart3,
        permission: Permission.AnalyticsView,
        children: [
          { label: "Drug Trend", href: "/analytics/drug-trend" },
          { label: "Network", href: "/analytics/network" },
          { label: "Member", href: "/analytics/member" },
          { label: "Financial", href: "/analytics/financial" },
          { label: "Data Quality", href: "/analytics/data-quality" },
        ],
      },
    ],
  },
  {
    label: "Admin",
    items: [
      { label: "Users", href: "/admin/users", icon: UserCog, permission: Permission.AdminFull },
      { label: "Tenants", href: "/admin/tenants", icon: Building, permission: Permission.AdminFull },
      { label: "Configuration", href: "/admin/config", icon: Settings, permission: Permission.AdminFull },
      { label: "Audit Log", href: "/admin/audit-log", icon: ScrollText, permission: Permission.AdminFull },
      { label: "System Health", href: "/admin/system-health", icon: Activity, permission: Permission.AdminFull },
    ],
  },
  {
    label: "Coming Soon",
    items: [
      { label: "Plan Design", href: "#", icon: Lock, comingSoon: true },
      { label: "Rules Engine", href: "#", icon: Lock, comingSoon: true },
      { label: "Adjudication", href: "#", icon: Lock, comingSoon: true },
      { label: "Prior Authorization", href: "#", icon: Lock, comingSoon: true },
      { label: "Rebate Management", href: "#", icon: Lock, comingSoon: true },
    ],
  },
];

const COLLAPSED_KEY = "ifx-sidebar-collapsed";
const EXPANDED_SECTIONS_KEY = "ifx-sidebar-expanded-sections";

export function Sidebar({ className }: { className?: string }) {
  const pathname = usePathname();
  const { user, hasPermission } = useAuth();
  const [collapsed, setCollapsed] = useState(false);
  const [expandedItems, setExpandedItems] = useState<Record<string, boolean>>({});
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    const storedCollapsed = localStorage.getItem(COLLAPSED_KEY);
    if (storedCollapsed === "true") setCollapsed(true);
    const storedExpanded = localStorage.getItem(EXPANDED_SECTIONS_KEY);
    if (storedExpanded) {
      try {
        setExpandedItems(JSON.parse(storedExpanded));
      } catch {
        // ignore
      }
    }
    setHydrated(true);
  }, []);

  // Auto-expand parent if any child is on the current pathname
  useEffect(() => {
    if (!hydrated) return;
    const next = { ...expandedItems };
    let changed = false;
    for (const section of NAV_SECTIONS) {
      for (const item of section.items) {
        if (item.children?.some((c) => pathname.startsWith(c.href) && c.href !== "/")) {
          if (!next[item.href]) {
            next[item.href] = true;
            changed = true;
          }
        }
      }
    }
    if (changed) setExpandedItems(next);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname, hydrated]);

  function toggleCollapse() {
    setCollapsed((c) => {
      const next = !c;
      localStorage.setItem(COLLAPSED_KEY, String(next));
      return next;
    });
  }

  function toggleExpand(href: string) {
    setExpandedItems((prev) => {
      const next = { ...prev, [href]: !prev[href] };
      localStorage.setItem(EXPANDED_SECTIONS_KEY, JSON.stringify(next));
      return next;
    });
  }

  function isActive(href: string) {
    if (href === "/") return pathname === "/";
    return pathname === href || pathname.startsWith(href + "/");
  }

  function canSeeItem(item: NavItem): boolean {
    if (item.comingSoon) return true;
    if (!user) return false;
    if (item.permission) return hasPermission(item.permission);
    return true;
  }

  return (
    <aside
      className={cn(
        "flex h-full flex-col border-r border-navy-700 bg-navy-900 transition-all duration-200",
        collapsed ? "w-16" : "w-64",
        className,
      )}
      aria-label="Main navigation"
    >
      {/* Logo */}
      <div className="flex h-14 items-center border-b border-navy-700 px-4 shrink-0">
        <Link
          href="/"
          className={cn("flex items-center gap-2", collapsed && "mx-auto")}
          aria-label="InfinityRx Home"
        >
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-teal-500 text-sm font-bold text-white">
            IFX
          </div>
          {!collapsed && (
            <span className="text-sm font-bold tracking-wide text-white">InfinityRx</span>
          )}
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-3" aria-label="Sidebar navigation">
        {NAV_SECTIONS.map((section, idx) => {
          const visibleItems = section.items.filter(canSeeItem);
          if (visibleItems.length === 0) return null;
          const isComingSoonSection = section.label === "Coming Soon";

          return (
            <div key={idx} className={cn("mb-3", isComingSoonSection && "mt-4 border-t border-navy-700 pt-3")}>
              {section.label && !collapsed && (
                <div className="mb-1 px-4 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                  {section.label}
                </div>
              )}
              <div className="space-y-0.5">
                {visibleItems.map((item) => (
                  <NavItemRow
                    key={item.label + item.href}
                    item={item}
                    pathname={pathname}
                    collapsed={collapsed}
                    isExpanded={!!expandedItems[item.href]}
                    onToggleExpand={() => toggleExpand(item.href)}
                    isActiveFn={isActive}
                  />
                ))}
              </div>
            </div>
          );
        })}
      </nav>

      {/* Collapse toggle */}
      <div className="border-t border-navy-700 p-2 shrink-0">
        <button
          onClick={toggleCollapse}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className={cn(
            "flex w-full items-center gap-2 rounded-md px-3 py-2 text-slate-400 transition-colors hover:bg-navy-700 hover:text-white",
            collapsed && "justify-center px-0",
          )}
        >
          {collapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <>
              <ChevronLeft className="h-4 w-4" />
              <span className="text-xs">Collapse</span>
            </>
          )}
        </button>
      </div>
    </aside>
  );
}

function NavItemRow({
  item,
  pathname,
  collapsed,
  isExpanded,
  onToggleExpand,
  isActiveFn,
}: {
  item: NavItem;
  pathname: string;
  collapsed: boolean;
  isExpanded: boolean;
  onToggleExpand: () => void;
  isActiveFn: (href: string) => boolean;
}) {
  const Icon = item.icon;
  const hasChildren = !!item.children?.length;
  const parentActive = isActiveFn(item.href);

  // Coming-soon item — non-clickable
  if (item.comingSoon) {
    return (
      <div
        className={cn(
          "flex items-center gap-3 px-4 py-2 cursor-default text-slate-600",
          collapsed && "justify-center px-0",
        )}
        title={collapsed ? `${item.label} — Available in Phase 5` : "Available in Phase 5"}
        aria-label={`${item.label} — coming soon`}
      >
        <Lock className="h-4 w-4 shrink-0 opacity-60" />
        {!collapsed && (
          <>
            <span className="flex-1 truncate text-sm opacity-60">{item.label}</span>
            <span className="rounded-full bg-navy-700/50 px-1.5 py-0.5 text-[9px] font-medium uppercase tracking-wide text-slate-500">
              Phase 5
            </span>
          </>
        )}
      </div>
    );
  }

  // Parent with children — expandable
  if (hasChildren && !collapsed) {
    return (
      <div>
        <div
          className={cn(
            "group relative flex items-center gap-3 pr-2 transition-colors",
            parentActive ? "text-teal-400" : "text-slate-300 hover:text-white",
          )}
        >
          {/* Active indicator bar */}
          {parentActive && (
            <span className="absolute left-0 top-1/2 h-6 w-0.5 -translate-y-1/2 rounded-r bg-teal-400" />
          )}
          <Link
            href={item.href}
            className={cn(
              "flex flex-1 items-center gap-3 rounded-md py-2 pl-4 text-sm font-medium transition-colors",
              parentActive ? "bg-teal-500/10" : "hover:bg-navy-700",
            )}
            aria-current={parentActive ? "page" : undefined}
          >
            <Icon className="h-4 w-4 shrink-0" />
            <span className="flex-1 truncate">{item.label}</span>
          </Link>
          <button
            onClick={onToggleExpand}
            aria-label={isExpanded ? `Collapse ${item.label}` : `Expand ${item.label}`}
            aria-expanded={isExpanded}
            className="rounded p-1 text-slate-500 transition-colors hover:bg-navy-700 hover:text-white"
          >
            <ChevronDown
              className={cn(
                "h-3.5 w-3.5 transition-transform duration-150",
                isExpanded ? "rotate-0" : "-rotate-90",
              )}
            />
          </button>
        </div>
        {isExpanded && (
          <div className="mt-0.5 ml-[26px] border-l border-navy-700 pl-2 space-y-0.5">
            {item.children!.map((child) => {
              const active = pathname === child.href || pathname.startsWith(child.href + "/");
              return (
                <Link
                  key={child.href}
                  href={child.href}
                  className={cn(
                    "block rounded-md px-3 py-1.5 text-xs transition-colors",
                    active
                      ? "bg-teal-500/10 font-medium text-teal-400"
                      : "text-slate-400 hover:bg-navy-700 hover:text-white",
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

  // Leaf or collapsed parent
  return (
    <div className="relative">
      {parentActive && (
        <span className="absolute left-0 top-1/2 h-6 w-0.5 -translate-y-1/2 rounded-r bg-teal-400" />
      )}
      <Link
        href={item.href}
        className={cn(
          "flex items-center gap-3 px-4 py-2 text-sm transition-colors",
          collapsed && "justify-center px-0",
          parentActive
            ? "bg-teal-500/10 font-medium text-teal-400"
            : "text-slate-300 hover:bg-navy-700 hover:text-white",
        )}
        title={collapsed ? item.label : undefined}
        aria-label={item.label}
        aria-current={parentActive ? "page" : undefined}
      >
        <Icon className="h-4 w-4 shrink-0" />
        {!collapsed && <span className="flex-1 truncate">{item.label}</span>}
        {!collapsed && item.badge && (
          <span className="ml-auto flex h-5 min-w-[20px] items-center justify-center rounded-full bg-red-500 px-1.5 text-[10px] font-bold text-white">
            {item.badge}
          </span>
        )}
      </Link>
    </div>
  );
}

// Suppress unused import warning — Role is referenced for potential future role gating
void Role;
