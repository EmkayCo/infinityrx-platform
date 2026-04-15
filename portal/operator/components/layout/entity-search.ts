import { isMockEnabled } from "@shared/lib/mock-data";
import { apiGet } from "@shared/lib/api-client";

export type EntityKind =
  | "claim"
  | "pharmacy"
  | "prescriber"
  | "member"
  | "investigation"
  | "invoice";

export interface EntitySearchResult {
  id: string;
  kind: EntityKind;
  primary: string;
  secondary?: string;
  href: string;
}

interface SearchableClaim {
  id: string;
  auth_number?: string;
  drug_name?: string;
  pharmacy_name?: string;
  member_id?: string;
}
interface SearchablePharmacy {
  npi: string;
  name?: string;
  ncpdp?: string;
  city?: string;
  state?: string;
}
interface SearchablePrescriber {
  npi: string;
  name?: string;
  specialty?: string;
}
interface SearchableMember {
  id?: string;
  member_id?: string;
  first_name?: string;
  last_name?: string;
}
interface SearchableInvestigation {
  id: string;
  subject_name?: string;
  category?: string;
  status?: string;
}
interface SearchableInvoice {
  id: string;
  invoice_number?: string;
  client_name?: string;
  status?: string;
}

async function safeList<T>(url: string): Promise<T[]> {
  try {
    const res = await apiGet<T[] | { items?: T[]; rows?: T[] }>(url);
    if (Array.isArray(res)) return res;
    if (res && typeof res === "object") {
      const anyRes = res as { items?: T[]; rows?: T[] };
      if (Array.isArray(anyRes.items)) return anyRes.items;
      if (Array.isArray(anyRes.rows)) return anyRes.rows;
    }
  } catch {
    // ignore — mock may not have this endpoint
  }
  return [];
}

/**
 * Search entities across the portal. Returns results grouped by kind.
 * Backed by mock handlers for now — each endpoint's handler either filters
 * or returns the full list (we filter client-side by query).
 */
export async function searchEntities(
  query: string,
  limit = 5,
): Promise<EntitySearchResult[]> {
  const q = query.trim().toLowerCase();
  if (q.length < 2) return [];
  if (!isMockEnabled && typeof window === "undefined") return [];

  const [claims, pharmacies, prescribers, members, investigations, invoices] =
    await Promise.all([
      safeList<SearchableClaim>("/billing/v1/claims"),
      safeList<SearchablePharmacy>("/api/v1/pharmacies"),
      safeList<SearchablePrescriber>("/api/v1/prescribers"),
      safeList<SearchableMember>("/api/v1/members"),
      safeList<SearchableInvestigation>("/api/v1/investigations"),
      safeList<SearchableInvoice>("/billing/v1/invoices"),
    ]);

  const results: EntitySearchResult[] = [];

  for (const c of claims) {
    if (
      c.id?.toLowerCase().includes(q) ||
      c.auth_number?.toLowerCase().includes(q) ||
      c.drug_name?.toLowerCase().includes(q) ||
      c.pharmacy_name?.toLowerCase().includes(q) ||
      c.member_id?.toLowerCase().includes(q)
    ) {
      results.push({
        id: c.id,
        kind: "claim",
        primary: c.auth_number ? `Auth #${c.auth_number}` : `Claim ${c.id.slice(0, 8)}`,
        secondary: [c.drug_name, c.pharmacy_name].filter(Boolean).join(" · "),
        href: `/claims/${c.id}`,
      });
      if (results.filter((r) => r.kind === "claim").length >= limit) break;
    }
  }

  for (const p of pharmacies) {
    if (!p.npi) continue;
    if (
      p.npi.includes(q) ||
      p.name?.toLowerCase().includes(q) ||
      p.ncpdp?.includes(q)
    ) {
      results.push({
        id: p.npi,
        kind: "pharmacy",
        primary: p.name ?? `NPI ${p.npi}`,
        secondary: [p.ncpdp && `NCPDP ${p.ncpdp}`, p.city, p.state]
          .filter(Boolean)
          .join(" · "),
        href: `/directories/pharmacies/${p.npi}`,
      });
      if (results.filter((r) => r.kind === "pharmacy").length >= limit) break;
    }
  }

  for (const p of prescribers) {
    if (!p.npi) continue;
    if (p.npi.includes(q) || p.name?.toLowerCase().includes(q)) {
      results.push({
        id: p.npi,
        kind: "prescriber",
        primary: p.name ?? `NPI ${p.npi}`,
        secondary: p.specialty,
        href: `/directories/prescribers/${p.npi}`,
      });
      if (results.filter((r) => r.kind === "prescriber").length >= limit) break;
    }
  }

  for (const m of members) {
    const memberId = m.member_id ?? m.id;
    if (!memberId) continue;
    const name = [m.first_name, m.last_name].filter(Boolean).join(" ");
    if (
      memberId.toLowerCase().includes(q) ||
      name.toLowerCase().includes(q)
    ) {
      results.push({
        id: memberId,
        kind: "member",
        primary: name || `Member ${memberId}`,
        secondary: memberId,
        href: `/directories/members/${memberId}`,
      });
      if (results.filter((r) => r.kind === "member").length >= limit) break;
    }
  }

  for (const inv of investigations) {
    if (
      inv.id?.toLowerCase().includes(q) ||
      inv.subject_name?.toLowerCase().includes(q) ||
      inv.category?.toLowerCase().includes(q)
    ) {
      results.push({
        id: inv.id,
        kind: "investigation",
        primary: inv.subject_name ?? `Investigation ${inv.id}`,
        secondary: [inv.category, inv.status].filter(Boolean).join(" · "),
        href: `/reclaimrx/investigations/${inv.id}`,
      });
      if (results.filter((r) => r.kind === "investigation").length >= limit) break;
    }
  }

  for (const inv of invoices) {
    if (
      inv.id?.toLowerCase().includes(q) ||
      inv.invoice_number?.toLowerCase().includes(q) ||
      inv.client_name?.toLowerCase().includes(q)
    ) {
      results.push({
        id: inv.id,
        kind: "invoice",
        primary: inv.invoice_number ?? `Invoice ${inv.id.slice(0, 8)}`,
        secondary: [inv.client_name, inv.status].filter(Boolean).join(" · "),
        href: `/accounting/invoices/${inv.id}`,
      });
      if (results.filter((r) => r.kind === "invoice").length >= limit) break;
    }
  }

  return results;
}
