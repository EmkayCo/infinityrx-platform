// src/search/FederatedSearchClient.ts
// BFF-side federated search client. Fans out to backend search endpoints in
// parallel, enforces a wall-time budget, merges and ranks results.
// Runs in Node.js environment (Next.js route handler).
import type { SearchResultRecord } from "./schemas.js";
import { rankResults } from "./rankResults.js";
import { ID_PATTERNS } from "./schemas.js";

export interface FederatedSearchOpts {
  prescriberDirectoryUrl: string;  // e.g. http://prescriber-directory:8010
  pharmacyDirectoryUrl: string;    // e.g. http://pharmacy-directory:8009
  drugDatabaseUrl: string;         // e.g. http://drug-database:8011
  budgetMs?: number;               // wall-time budget (default 300)
  limitPerDataset?: number;        // per-backend limit (default 5)
}

interface DatasetFetchResult {
  records: SearchResultRecord[];
  dataset: string;
  ok: boolean;
}

export class FederatedSearchClient {
  private opts: Required<FederatedSearchOpts>;

  constructor(opts: FederatedSearchOpts) {
    this.opts = { budgetMs: 300, limitPerDataset: 5, ...opts };
  }

  /** ID shortcut: detect NPI/NDC/HCPCS/ICD-10 and route to exact-match endpoint */
  detectIdShortcut(q: string): { kind: "npi" | "ndc" | "hcpcs" | "icd10"; value: string } | null {
    if (!q) return null;
    if (ID_PATTERNS.NPI.test(q)) return { kind: "npi", value: q };
    if (ID_PATTERNS.NDC_11.test(q) || ID_PATTERNS.NDC_HYPHENATED.test(q)) return { kind: "ndc", value: q };
    if (ID_PATTERNS.HCPCS.test(q)) return { kind: "hcpcs", value: q };
    if (ID_PATTERNS.ICD10.test(q)) return { kind: "icd10", value: q };
    return null;
  }

  async search(
    q: string,
    correlationId: string,
  ): Promise<{ results: SearchResultRecord[]; timedOutDatasets: string[] }> {
    if (!q.trim()) {
      return { results: [], timedOutDatasets: [] };
    }

    const deadline = Date.now() + this.opts.budgetMs;
    const headers: Record<string, string> = {
      "x-correlation-id": correlationId,
      "content-type": "application/json",
    };
    const limit = this.opts.limitPerDataset;

    // Races each fetch against the remaining wall-time budget. Returns fallback on timeout.
    // Always races (never short-circuits) so that already-resolved promises (e.g. in tests)
    // can win even when remaining budget is near zero.
    const withDeadline = async <T>(p: Promise<T>, fallback: T): Promise<T> => {
      const remaining = deadline - Date.now();
      const timeoutMs = Math.max(0, remaining);
      const timeout = new Promise<T>((res) =>
        setTimeout(() => res(fallback), timeoutMs),
      );
      return Promise.race([p, timeout]);
    };

    const fetches: Promise<DatasetFetchResult>[] = [
      withDeadline(
        fetch(
          `${this.opts.prescriberDirectoryUrl}/api/v1/prescribers/search?q=${encodeURIComponent(q)}&limit=${limit}`,
          { headers },
        )
          .then((r) => r.json())
          .then((data: { results?: Record<string, unknown>[] }) => ({
            records: (data.results ?? []).map((p) => ({
              dataset: "nppes" as const,
              id: String(p.npi ?? ""),
              display: String(p.name ?? p.display ?? ""),
              secondary: String(p.specialty ?? ""),
              source_date: p.source_date ? String(p.source_date) : null,
              run_id: p.run_id ? String(p.run_id) : null,
            })),
            dataset: "nppes",
            ok: true,
          }))
          .catch(() => ({ records: [], dataset: "nppes", ok: false })),
        { records: [], dataset: "nppes", ok: false },
      ),
      withDeadline(
        fetch(
          `${this.opts.pharmacyDirectoryUrl}/api/v1/pharmacies/search?q=${encodeURIComponent(q)}&limit=${limit}`,
          { headers },
        )
          .then((r) => r.json())
          .then((data: { results?: Record<string, unknown>[] }) => ({
            records: (data.results ?? []).map((p) => ({
              dataset: "ncpdp" as const,
              id: String(p.nabp ?? ""),
              display: String(p.name ?? p.display ?? ""),
              secondary: String(p.city ?? ""),
              source_date: p.source_date ? String(p.source_date) : null,
              run_id: p.run_id ? String(p.run_id) : null,
            })),
            dataset: "ncpdp",
            ok: true,
          }))
          .catch(() => ({ records: [], dataset: "ncpdp", ok: false })),
        { records: [], dataset: "ncpdp", ok: false },
      ),
      withDeadline(
        fetch(
          `${this.opts.drugDatabaseUrl}/api/v1/drugs/search?q=${encodeURIComponent(q)}&limit=${limit}`,
          { headers },
        )
          .then((r) => r.json())
          .then((data: { results?: Record<string, unknown>[] }) => ({
            records: (data.results ?? []).map((d) => ({
              dataset: "fda_ndc" as const,
              id: String(d.ndc ?? ""),
              display: String(d.proprietary_name ?? d.display ?? ""),
              secondary: String(d.nonproprietary_name ?? ""),
              source_date: d.source_date ? String(d.source_date) : null,
              run_id: d.run_id ? String(d.run_id) : null,
            })),
            dataset: "fda_ndc",
            ok: true,
          }))
          .catch(() => ({ records: [], dataset: "fda_ndc", ok: false })),
        { records: [], dataset: "fda_ndc", ok: false },
      ),
    ];

    const settled = await Promise.all(fetches);
    const timedOutDatasets = settled.filter((s) => !s.ok).map((s) => s.dataset);
    const allRecords = settled.flatMap((s) => s.records);
    return { results: rankResults(allRecords, q), timedOutDatasets };
  }
}
