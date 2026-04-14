"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  CreditCard,
  DollarSign,
  ShieldAlert,
  BarChart2,
  Pill,
  Stethoscope,
  Database,
  Users,
  FileText,
  Zap,
  TrendingUp,
  Settings,
  ChevronLeft,
  ChevronRight,
  Lock,
} from "lucide-react";
import { cn } from "@shared/lib/format";
import { useAuth } from "@shared/hooks/use-auth";
import { Permission, Role } from "@shared/types/auth";
import { FEATURE_FLAGS } from "@shared/lib/constants";

interface NavItem {
  label: string;
  href: string;
  icon: React.ElementType;
  permission?: Permission;
  badge?: string;
  comingSoon?: boolean;
  children?: NavItem[];
}

const NAV_SECTIONS: { label?: string; items: NavItem[] }[] = [
  {
    items: [
      {
        label: "Dashboard",
        href: "/",
        icon: LayoutDashboard,
        permission: Permission.DashboardView,
      },
    ],
  },
  {
    label: "Operations",
    items: [
      { label: "Billing", href: "/billing", icon: CreditCard, permission: Permission.BillingView },
      { label: "Payments", href: "/payments", icon: DollarSign, permission: Permission.PaymentsView },
      { label: "ReclaimRx", href: "/reclaimrx", icon: ShieldAlert, permission: Permission.ReclaimRxView },
      { label: "Reporting", href: "/reporting", icon: BarChart2, permission: Permission.ReportingView },
    ],
  },
  {
    label: "Directories",
    items: [
      { label: "Pharmacy Directory", href: "/directories/pharmacy", icon: Pill, permission: Permission.DirectoriesView },
      { label: "Prescriber Directory", href: "/directories/prescribers", icon: Stethoscope, permission: Permission.DirectoriesView },
      { label: "Drug Database", href: "/directories/drugs", icon: Database, permission: Permission.DirectoriesView },
      { label: "Member Management", href: "/directories/members", icon: Users, permission: Permission.DirectoriesView },
    ],
  },
  {
    label: "Advanced",
    items: [
      { label: "EDI Operations", href: "/edi", icon: FileText, permission: Permission.EDIView },
      { label: "Medical Claims", href: "/medical-claims", icon: FileText, permission: Permission.DirectoriesView },
      { label: "AI / NLP", href: "/ai-nlp", icon: Zap, permission: Permission.AnalyticsView },
      { label: "Analytics", href: "/analytics", icon: TrendingUp, permission: Permission.AnalyticsView },
    ],
  },
  {
    label: "Phase 5",
    items: [
      { label: "Plan Design", href: "/plan-design", icon: Settings, comingSoon: !FEATURE_FLAGS.planDesign },
      { label: "Adjudication", href: "/adjudication", icon: Settings, comingSoon: !FEATURE_FLAGS.adjudication },
      { label: "Prior Auth", href: "/prior-auth", icon: Settings, comingSoon: !FEATURE_FLAGS.priorAuth },
      { label: "Switch Connectivity", href: "/switch", icon: Settings, comingSoon: !FEATURE_FLAGS.switchConnectivity },
      { label: "Rebate Management", href: "/rebates", icon: Settings, comingSoon: !FEATURE_FLAGS.rebateManagement },
    ],
  },
  {
    label: "Admin",
    items: [
      { label: "Users", href: "/admin/users", icon: Users, permission: Permission.AdminFull },
      { label: "Tenants", href: "/admin/tenants", icon: Settings, permission: Permission.AdminFull },
      { label: "Audit Log", href: "/admin/audit-log", icon: FileText, permission: Permission.AdminFull },
      { label: "System Health", href: "/admin/system-health", icon: ShieldAlert, permission: Permission.AdminFull },
    ],
  },
];

const COLLAPSED_KEY = "ifx-sidebar-collapsed";

interface SidebarProps {
  className?: string;
}

export function Sidebar({ className }: SidebarProps) {
  const pathname = usePathname();
  const { user, hasPermission } = useAuth();
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem(COLLAPSED_KEY);
    if (stored === "true") setCollapsed(true);
  }, []);

  function toggleCollapse() {
    setCollapsed((c) => {
      const next = !c;
      localStorage.setItem(COLLAPSED_KEY, String(next));
      return next;
    });
  }

  function isActive(href: string) {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  }

  function canSeeItem(item: NavItem): boolean {
    if (!user) return false;
    if (user.role === Role.Admin) return true;
    if (item.permission) return hasPermission(item.permission);
    return !item.comingSoon;
  }

  return (
    <aside
      className={cn(
        "flex h-full flex-col border-r bg-navy-900 transition-all duration-200",
        collapsed ? "w-16" : "w-64",
        className
      )}
      aria-label="Main navigation"
    >
      {/* Logo */}
      <div className="flex h-14 items-center border-b border-navy-700 px-4">
        {!collapsed ? (
          <Link href="/" className="flex items-center gap-2" aria-label="InfinityRx Home">
            <div className="flex h-8 w-8 items-center justify-center rounded-md bg-teal-500 font-bold text-white text-sm">
              IFX
            </div>
            <span className="font-bold text-white text-sm tracking-wide">InfinityRx</span>
          </Link>
        ) : (
          <Link href="/" className="mx-auto" aria-label="InfinityRx Home">
            <div className="flex h-8 w-8 items-center justify-center rounded-md bg-teal-500 font-bold text-white text-sm">
              IFX
            </div>
          </Link>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-4 scrollbar-thin" aria-label="Sidebar navigation">
        {NAV_SECTIONS.map((section, idx) => {
          const visibleItems = section.items.filter(canSeeItem);
          if (visibleItems.length === 0) return null;

          return (
            <div key={idx} className="mb-2">
              {section.label && !collapsed && (
                <div className="mb-1 px-4 text-xs font-semibold uppercase tracking-wider text-navy-500/70 text-slate-500">
                  {section.label}
                </div>
              )}
              {visibleItems.map((item) => (
                <NavLink
                  key={item.href}
                  item={item}
                  isActive={isActive(item.href)}
                  collapsed={collapsed}
                />
              ))}
            </div>
          );
        })}
      </nav>

      {/* Collapse toggle */}
      <div className="border-t border-navy-700 p-2">
        <button
          onClick={toggleCollapse}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className={cn(
            "flex w-full items-center gap-2 rounded-md px-3 py-2 text-slate-400 hover:bg-navy-700 hover:text-white transition-colors",
            collapsed && "justify-center"
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

interface NavLinkProps {
  item: NavItem;
  isActive: boolean;
  collapsed: boolean;
}

function NavLink({ item, isActive, collapsed }: NavLinkProps) {
  const Icon = item.icon;

  if (item.comingSoon) {
    return (
      <div
        className={cn(
          "flex items-center gap-3 px-4 py-2 text-slate-600 cursor-default",
          collapsed && "justify-center px-2"
        )}
        title={collapsed ? item.label : undefined}
        aria-label={item.comingSoon ? `${item.label} — Coming Soon` : item.label}
      >
        <Lock className="h-4 w-4 shrink-0 opacity-50" />
        {!collapsed && (
          <span className="text-sm truncate opacity-50">{item.label}</span>
        )}
        {!collapsed && (
          <span className="ml-auto text-xs rounded-full bg-muted px-1.5 py-0.5 text-muted-foreground">
            Soon
          </span>
        )}
      </div>
    );
  }

  return (
    <Link
      href={item.href}
      className={cn(
        "flex items-center gap-3 px-4 py-2 text-sm transition-colors",
        collapsed && "justify-center px-2",
        isActive
          ? "bg-teal-500/20 text-teal-400 font-medium"
          : "text-slate-400 hover:bg-navy-700 hover:text-white"
      )}
      title={collapsed ? item.label : undefined}
      aria-label={item.label}
      aria-current={isActive ? "page" : undefined}
    >
      <Icon className="h-4 w-4 shrink-0" />
      {!collapsed && <span className="truncate">{item.label}</span>}
      {!collapsed && item.badge && (
        <span className="ml-auto flex h-5 w-5 items-center justify-center rounded-full bg-red-500 text-xs font-bold text-white">
          {item.badge}
        </span>
      )}
    </Link>
  );
}
