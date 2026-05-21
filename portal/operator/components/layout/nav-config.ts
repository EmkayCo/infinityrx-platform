import {
  LayoutDashboard,
  Pill,
  FileText,
  DollarSign,
  ShieldAlert,
  BarChart3,
  BookOpen,
  Users,
  Radio,
  MapPin,
  FileBarChart,
  Settings,
  Building2,
  type LucideIcon,
} from "lucide-react";
import { Permission } from "@shared/types/auth";

export interface NavLeaf {
  label: string;
  href: string;
  permission?: Permission;
}

export interface NavModule {
  label: string;
  icon: LucideIcon;
  href: string; // primary href — first child or module landing page
  permission?: Permission;
  children?: NavLeaf[];
}

/**
 * Authoritative navigation hierarchy for the ICP Operator Portal.
 * Both the Sidebar and SectionTabs derive from this single source.
 */
export const NAV_MODULES: NavModule[] = [
  {
    label: "Dashboard",
    icon: LayoutDashboard,
    href: "/",
    permission: Permission.DashboardView,
  },
  {
    label: "Programs",
    icon: Pill,
    href: "/programs",
    children: [
      { label: "Program Overview", href: "/programs" },
      { label: "Enrollment", href: "/programs/enrollment" },
      { label: "Budget & Forecast", href: "/programs/budget" },
      { label: "Program Configuration", href: "/programs/config" },
    ],
  },
  {
    label: "Claims",
    icon: FileText,
    href: "/claims",
    permission: Permission.BillingView,
    children: [
      { label: "Claims Explorer", href: "/claims" },
      { label: "Claim Lookup", href: "/claims/lookup" },
      { label: "Manual Claims", href: "/claims/manual" },
      { label: "PA Override", href: "/claims/pa-override" },
    ],
  },
  {
    label: "Billing & PaySync",
    icon: DollarSign,
    href: "/accounting/cycles",
    permission: Permission.BillingView,
    children: [
      { label: "Billing Cycles", href: "/accounting/cycles" },
      { label: "Payments & Batches", href: "/accounting/payments" },
      { label: "NACHA", href: "/accounting/nacha" },
      { label: "Journal Entries", href: "/accounting/journal-entries" },
      { label: "PaySync Dashboard", href: "/admin/paysync", permission: Permission.AdminFull },
      { label: "Uploads", href: "/admin/paysync/uploads", permission: Permission.AdminFull },
      { label: "Cycles", href: "/admin/paysync/cycles", permission: Permission.AdminFull },
      { label: "Batches", href: "/admin/paysync/batches", permission: Permission.AdminFull },
      { label: "Carryovers", href: "/admin/paysync/carryovers", permission: Permission.AdminFull },
      { label: "Invoices", href: "/admin/paysync/invoices", permission: Permission.AdminFull },
      { label: "Payment Runs", href: "/admin/paysync/payment-runs", permission: Permission.AdminFull },
      { label: "Files", href: "/admin/paysync/files", permission: Permission.AdminFull },
      { label: "Bank Settlements", href: "/admin/paysync/bank-settlements", permission: Permission.AdminFull },
      { label: "Reconciliations", href: "/admin/paysync/reconciliations", permission: Permission.AdminFull },
      { label: "Journal", href: "/admin/paysync/journal", permission: Permission.AdminFull },
      { label: "Echo Spec 400", href: "/admin/paysync/echo", permission: Permission.AdminFull },
      { label: "Setup", href: "/admin/paysync/setup", permission: Permission.AdminFull },
      { label: "Cycle Schedules", href: "/admin/paysync/setup/cycle-schedules", permission: Permission.AdminFull },
      { label: "Export Templates", href: "/admin/paysync/setup/export-templates", permission: Permission.AdminFull },
      { label: "Email Templates", href: "/admin/paysync/setup/email-templates", permission: Permission.AdminFull },
      { label: "Email Recipients", href: "/admin/paysync/setup/email-recipients", permission: Permission.AdminFull },
      { label: "GL Mappings", href: "/admin/paysync/setup/gl-account-mappings", permission: Permission.AdminFull },
      { label: "Invoice Sequences", href: "/admin/paysync/setup/invoice-sequences", permission: Permission.AdminFull },
    ],
  },
  {
    label: "ReclaimRx",
    icon: ShieldAlert,
    href: "/reclaimrx",
    permission: Permission.ReclaimRxView,
    children: [
      { label: "GTN Dashboard", href: "/reclaimrx" },
      { label: "Leakage Monitor", href: "/reclaimrx/leakage" },
      { label: "Investigations", href: "/reclaimrx/investigations" },
      { label: "Pharmacy Risk Scores", href: "/reclaimrx/risk" },
      { label: "Recovery Tracking", href: "/reclaimrx/recovery" },
      { label: "Case Wizard", href: "/reclaimrx/wizard" },
    ],
  },
  {
    label: "Analytics",
    icon: BarChart3,
    href: "/analytics/claims",
    permission: Permission.AnalyticsView,
    children: [
      { label: "Claim Summary", href: "/analytics/claims" },
      { label: "Fill Performance", href: "/analytics/fills" },
      { label: "Adherence", href: "/analytics/adherence" },
      { label: "Pharmacy Insights", href: "/analytics/pharmacies" },
      { label: "Geographic Analysis", href: "/analytics/geography" },
      { label: "Trend Analysis", href: "/analytics/trends" },
    ],
  },
  {
    label: "Directories",
    icon: BookOpen,
    href: "/directories/pharmacies",
    permission: Permission.DirectoriesView,
    children: [
      { label: "Pharmacies", href: "/directories/pharmacies" },
      { label: "Prescribers", href: "/directories/prescribers" },
      { label: "Drugs / Formulary", href: "/directories/drugs" },
      { label: "Codes — HCPCS", href: "/directories/codes/hcpcs" },
      { label: "Codes — ICD-10", href: "/directories/codes/icd10" },
      { label: "Pricing", href: "/directories/pricing" },
      { label: "Exclusions", href: "/directories/exclusions" },
      { label: "Members", href: "/directories/members" },
      { label: "Ingestion Console", href: "/directories/ingestion" },
      { label: "Data Quality", href: "/directories/quality" },
      { label: "Audit Log", href: "/directories/audit" },
    ],
  },
  {
    label: "Client Management",
    icon: Users,
    href: "/clients",
    children: [
      { label: "Companies", href: "/clients" },
      { label: "Client Programs", href: "/clients/programs" },
      { label: "Fee Configuration", href: "/clients/fees" },
      { label: "Preferred Networks", href: "/clients/networks" },
      { label: "Exceptions", href: "/clients/exceptions" },
      { label: "Cardholder IDs", href: "/clients/cardholders" },
      { label: "State Rules", href: "/clients/states" },
      { label: "Portal Access", href: "/clients/portal-access" },
    ],
  },
  {
    label: "EDI",
    icon: Radio,
    href: "/edi/monitor",
    permission: Permission.EDIView,
    children: [
      { label: "Monitor", href: "/edi/monitor" },
      { label: "Transactions", href: "/edi/transactions" },
      { label: "Partners", href: "/edi/partners" },
      { label: "Certificates", href: "/edi/certs" },
    ],
  },
  {
    label: "Network",
    icon: MapPin,
    href: "/network/locator",
    children: [
      { label: "Pharmacy Locator", href: "/network/locator" },
      { label: "Credentialing", href: "/network/credentialing" },
    ],
  },
  {
    label: "Reporting",
    icon: FileBarChart,
    href: "/reporting/library",
    permission: Permission.ReportingView,
    children: [
      { label: "Report Library", href: "/reporting/library" },
      { label: "Report Builder", href: "/reporting/builder" },
      { label: "Scheduled Reports", href: "/reporting/scheduled" },
    ],
  },
  {
    // Renamed from "Network" to avoid duplicate React key with the operator
    // "Network" group above (Sidebar keys ModuleRow by mod.label).
    label: "Network Admin",
    icon: Building2,
    href: "/admin/network/pay-to-entities",
    permission: Permission.AdminFull,
    children: [
      { label: "Pay-To Entities", href: "/admin/network/pay-to-entities" },
      { label: "Chain Membership", href: "/admin/network/chain-membership" },
      { label: "Banking Discrepancies", href: "/admin/network/banking-discrepancies" },
      { label: "Tenant ACH Origination", href: "/admin/network/tenant-ach-origination" },
    ],
  },
  {
    label: "Admin",
    icon: Settings,
    href: "/admin/users",
    permission: Permission.AdminFull,
    children: [
      { label: "Users & Roles", href: "/admin/users" },
      { label: "Tenant Settings", href: "/admin/tenants" },
      { label: "System Health", href: "/admin/system-health" },
      { label: "Configuration", href: "/admin/config" },
      { label: "Audit Log", href: "/admin/audit-log" },
      { label: "Encryption Tools", href: "/admin/encryption" },
    ],
  },
];

/**
 * Find which module owns a given pathname. Returns null for unknown paths.
 */
export function findActiveModule(pathname: string): NavModule | null {
  // Exact dashboard match
  if (pathname === "/") return NAV_MODULES[0] ?? null;

  // Prefer longest-prefix child match (so /clients/programs beats /clients)
  let best: { module: NavModule; len: number } | null = null;
  for (const mod of NAV_MODULES) {
    if (mod.children) {
      for (const child of mod.children) {
        if (pathname === child.href || pathname.startsWith(child.href + "/")) {
          if (!best || child.href.length > best.len) {
            best = { module: mod, len: child.href.length };
          }
        }
      }
    } else if (pathname === mod.href || pathname.startsWith(mod.href + "/")) {
      if (!best || mod.href.length > best.len) {
        best = { module: mod, len: mod.href.length };
      }
    }
  }
  return best?.module ?? null;
}

/**
 * Find which leaf (sub-item) is active for a given pathname.
 */
export function findActiveLeaf(pathname: string, module: NavModule): NavLeaf | null {
  if (!module.children) return null;
  let best: { leaf: NavLeaf; len: number } | null = null;
  for (const child of module.children) {
    if (pathname === child.href || pathname.startsWith(child.href + "/")) {
      if (!best || child.href.length > best.len) {
        best = { leaf: child, len: child.href.length };
      }
    }
  }
  return best?.leaf ?? null;
}
