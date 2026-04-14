import { isoDate, makeUUID, PRIMARY_TENANT, TENANT_IDS } from "./prng";
import type { ActivityEvent } from "@shared/types/common";
import { Role } from "@shared/types/auth";

export interface UserRow {
  id: string;
  email: string;
  name: string;
  role: Role;
  tenant_id: string;
  mfa_enrolled: boolean;
  active: boolean;
  last_login: string | null;
  created_at: string;
}

export interface TenantSettings {
  id: string;
  name: string;
  slug: string;
  status: "active" | "inactive" | "trial";
  mfa_required: boolean;
  feature_flags: Record<string, boolean>;
  created_at: string;
  updated_at: string;
  user_count: number;
  claim_count_ytd: number;
}

export const USERS: UserRow[] = [
  {
    id: makeUUID(60000),
    email: "sarah.chen@infinityrx.com",
    name: "Sarah Chen",
    role: Role.Admin,
    tenant_id: PRIMARY_TENANT,
    mfa_enrolled: true,
    active: true,
    last_login: isoDate(-1),
    created_at: isoDate(-365),
  },
  {
    id: makeUUID(60001),
    email: "marcus.rivera@infinityrx.com",
    name: "Marcus Rivera",
    role: Role.BillingOperator,
    tenant_id: PRIMARY_TENANT,
    mfa_enrolled: true,
    active: true,
    last_login: isoDate(0),
    created_at: isoDate(-180),
  },
  {
    id: makeUUID(60002),
    email: "priya.nair@infinityrx.com",
    name: "Priya Nair",
    role: Role.FWAInvestigator,
    tenant_id: PRIMARY_TENANT,
    mfa_enrolled: true,
    active: true,
    last_login: isoDate(0),
    created_at: isoDate(-270),
  },
  {
    id: makeUUID(60003),
    email: "james.okafor@infinityrx.com",
    name: "James Okafor",
    role: Role.FWAInvestigator,
    tenant_id: PRIMARY_TENANT,
    mfa_enrolled: true,
    active: true,
    last_login: isoDate(-2),
    created_at: isoDate(-200),
  },
  {
    id: makeUUID(60004),
    email: "elena.vasquez@clientdomain.com",
    name: "Elena Vasquez",
    role: Role.ClientManager,
    tenant_id: PRIMARY_TENANT,
    mfa_enrolled: false,
    active: true,
    last_login: isoDate(-3),
    created_at: isoDate(-90),
  },
  {
    id: makeUUID(60005),
    email: "thomas.becker@clientdomain.com",
    name: "Thomas Becker",
    role: Role.ClientManager,
    tenant_id: PRIMARY_TENANT,
    mfa_enrolled: true,
    active: true,
    last_login: isoDate(-1),
    created_at: isoDate(-120),
  },
  {
    id: makeUUID(60006),
    email: "michelle.park@clientdomain.com",
    name: "Michelle Park",
    role: Role.Viewer,
    tenant_id: PRIMARY_TENANT,
    mfa_enrolled: false,
    active: true,
    last_login: isoDate(-7),
    created_at: isoDate(-60),
  },
  {
    id: makeUUID(60007),
    email: "david.santos@infinityrx.com",
    name: "David Santos",
    role: Role.BillingOperator,
    tenant_id: PRIMARY_TENANT,
    mfa_enrolled: true,
    active: true,
    last_login: isoDate(-1),
    created_at: isoDate(-150),
  },
  {
    id: makeUUID(60008),
    email: "karen.obrien@infinityrx.com",
    name: "Karen O'Brien",
    role: Role.Admin,
    tenant_id: PRIMARY_TENANT,
    mfa_enrolled: true,
    active: true,
    last_login: isoDate(-4),
    created_at: isoDate(-400),
  },
  {
    id: makeUUID(60009),
    email: "alex.kim@clientdomain.com",
    name: "Alex Kim",
    role: Role.Viewer,
    tenant_id: PRIMARY_TENANT,
    mfa_enrolled: false,
    active: false,
    last_login: isoDate(-30),
    created_at: isoDate(-45),
  },
  {
    id: makeUUID(60010),
    email: "robert.torres@infinityrx.com",
    name: "Robert Torres",
    role: Role.FWAInvestigator,
    tenant_id: PRIMARY_TENANT,
    mfa_enrolled: true,
    active: true,
    last_login: isoDate(-1),
    created_at: isoDate(-310),
  },
  {
    id: makeUUID(60011),
    email: "linda.wu@clientdomain.com",
    name: "Linda Wu",
    role: Role.ClientManager,
    tenant_id: PRIMARY_TENANT,
    mfa_enrolled: true,
    active: true,
    last_login: isoDate(-2),
    created_at: isoDate(-80),
  },
];

export const TENANTS: TenantSettings[] = [
  {
    id: TENANT_IDS[0],
    name: "InfinityRx Internal",
    slug: "infinityrx",
    status: "active",
    mfa_required: true,
    feature_flags: { plan_design: false, adjudication: false, prior_auth: false, rebate_management: true },
    created_at: isoDate(-730),
    updated_at: isoDate(-1),
    user_count: 12,
    claim_count_ytd: 284750,
  },
  {
    id: TENANT_IDS[1],
    name: "Acme Health Partners",
    slug: "acme-health",
    status: "active",
    mfa_required: true,
    feature_flags: { plan_design: false, adjudication: false, prior_auth: true, rebate_management: false },
    created_at: isoDate(-365),
    updated_at: isoDate(-7),
    user_count: 45,
    claim_count_ytd: 124500,
  },
  {
    id: TENANT_IDS[2],
    name: "BlueStar Benefits Group",
    slug: "bluestar",
    status: "active",
    mfa_required: false,
    feature_flags: { plan_design: false, adjudication: false, prior_auth: false, rebate_management: false },
    created_at: isoDate(-200),
    updated_at: isoDate(-14),
    user_count: 23,
    claim_count_ytd: 87320,
  },
  {
    id: TENANT_IDS[3],
    name: "ClearPath Managed Care",
    slug: "clearpath",
    status: "trial",
    mfa_required: false,
    feature_flags: { plan_design: false, adjudication: false, prior_auth: false, rebate_management: false },
    created_at: isoDate(-30),
    updated_at: isoDate(-2),
    user_count: 5,
    claim_count_ytd: 0,
  },
];

export const AUDIT_ENTRIES = Array.from({ length: 50 }, (_, i) => {
  const actions = [
    "phi_access",
    "billing_cycle_approved",
    "payment_batch_transmitted",
    "user_role_changed",
    "login",
    "logout",
    "claim_status_updated",
    "investigation_assigned",
  ] as const;
  const action = actions[i % actions.length];
  const users = ["sarah.chen", "marcus.rivera", "priya.nair", "james.okafor", "elena.vasquez"];
  const user = users[i % users.length];

  return {
    id: makeUUID(80000 + i),
    tenant_id: PRIMARY_TENANT,
    user_id: makeUUID(60000 + (i % 5)),
    user_name: user,
    action,
    entity_type: ["phi_access", "claim_status_updated"].includes(action) ? "claim" : "system",
    entity_id: makeUUID(90000 + i),
    ip_address: `10.0.${Math.floor(i / 256)}.${i % 256}`,
    created_at: isoDate(-Math.floor(i / 5)),
    details: `Action: ${action} performed by ${user}`,
  };
});
