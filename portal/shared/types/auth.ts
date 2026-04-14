export enum Role {
  Admin = "admin",
  BillingOperator = "billing_operator",
  FWAInvestigator = "fwa_investigator",
  ClientManager = "client_manager",
  Viewer = "viewer",
}

export enum Permission {
  // Dashboard
  DashboardView = "dashboard:view",
  DashboardBillingWidgets = "dashboard:billing_widgets",
  DashboardFWAWidgets = "dashboard:fwa_widgets",
  DashboardClientWidgets = "dashboard:client_widgets",

  // Billing
  BillingFull = "billing:full",
  BillingView = "billing:view",

  // Payments
  PaymentsFull = "payments:full",
  PaymentsView = "payments:view",

  // ReclaimRx
  ReclaimRxFull = "reclaimrx:full",
  ReclaimRxView = "reclaimrx:view",

  // Reporting
  ReportingGenerate = "reporting:generate",
  ReportingFull = "reporting:full",
  ReportingView = "reporting:view",

  // Directories
  DirectoriesFull = "directories:full",
  DirectoriesView = "directories:view",

  // EDI
  EDIFull = "edi:full",
  EDIView = "edi:view",

  // Analytics
  AnalyticsFull = "analytics:full",
  AnalyticsView = "analytics:view",

  // Admin
  AdminFull = "admin:full",
}

export const ROLE_PERMISSIONS: Record<Role, Permission[]> = {
  [Role.Admin]: Object.values(Permission),
  [Role.BillingOperator]: [
    Permission.DashboardView,
    Permission.DashboardBillingWidgets,
    Permission.BillingFull,
    Permission.PaymentsView,
    Permission.ReclaimRxView,
    Permission.ReportingGenerate,
    Permission.DirectoriesView,
    Permission.EDIView,
    Permission.AnalyticsView,
  ],
  [Role.FWAInvestigator]: [
    Permission.DashboardView,
    Permission.DashboardFWAWidgets,
    Permission.BillingView,
    Permission.PaymentsView,
    Permission.ReclaimRxFull,
    Permission.ReportingGenerate,
    Permission.DirectoriesView,
    Permission.AnalyticsView,
  ],
  [Role.ClientManager]: [
    Permission.DashboardView,
    Permission.DashboardClientWidgets,
    Permission.BillingView,
    Permission.PaymentsView,
    Permission.ReclaimRxView,
    Permission.ReportingFull,
    Permission.DirectoriesFull,
    Permission.EDIView,
    Permission.AnalyticsFull,
  ],
  [Role.Viewer]: [
    Permission.DashboardView,
    Permission.BillingView,
    Permission.PaymentsView,
    Permission.ReclaimRxView,
    Permission.ReportingView,
    Permission.DirectoriesView,
    Permission.EDIView,
    Permission.AnalyticsView,
  ],
};

export interface User {
  id: string;
  email: string;
  name: string;
  role: Role;
  tenant_id: string;
  avatar_url?: string;
  mfa_enrolled: boolean;
  permissions: Permission[];
}

export interface Session {
  user: User;
  access_token: string;
  refresh_token: string;
  expires_at: number;
}
