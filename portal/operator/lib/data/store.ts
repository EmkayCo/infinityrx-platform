/**
 * In-memory server-side cache for InfinityRx claims data.
 * Lazy-loads on first call; lives for the process lifetime.
 * Import ONLY from server-side code (API routes, Server Components).
 *
 * @serverOnly — this module must not be imported by client components.
 */

import * as fs from "fs/promises";
import * as path from "path";
import type { ParsedClaim, Aggregations } from "./types";
import { parseFile } from "./parser";

// ── Paths ─────────────────────────────────────────────────────────────────────
// Raw source files (.txt, .xlsx) live outside /public so they are NOT
// served as static assets. Aggregated JSON outputs stay in /public so the
// browser-side mock layer (loadAgg) can still fetch them over HTTP.
const SOURCE_DIR = path.join(process.cwd(), "lib", "data", "sources");
const AGG_DIR = path.join(process.cwd(), "public", "data", "aggregated");

// ── Module-level cache ────────────────────────────────────────────────────────
interface Store {
  claims: ParsedClaim[];
  aggregations: Aggregations;
}

let _storePromise: Promise<Store> | null = null;

async function buildGroupMap(): Promise<Map<string, string>> {
  const start = Date.now();
  const map = new Map<string, string>();
  const { default: ExcelJS } = await import("exceljs");
  const wb = new ExcelJS.Workbook();
  await wb.xlsx.readFile(path.join(SOURCE_DIR, "client to groupid mappings.xlsx"));
  const ws = wb.worksheets[0];
  ws.eachRow((row, rowIndex) => {
    if (rowIndex === 1) return;
    const vals = row.values as (string | number | null)[];
    const company = vals[1];
    const groupId = vals[2];
    if (company && groupId) {
      map.set(String(groupId).trim(), String(company).trim());
    }
  });
  console.log(`[store] group map: ${map.size} entries in ${Date.now() - start}ms`);
  return map;
}

async function readJson<T>(filename: string): Promise<T> {
  const start = Date.now();
  const text = await fs.readFile(path.join(AGG_DIR, filename), "utf-8");
  const result = JSON.parse(text) as T;
  const ms = Date.now() - start;
  if (ms > 50 || text.length > 500_000) {
    console.log(
      `[store] aggregated/${filename}: ${ms}ms, ${(text.length / 1024 / 1024).toFixed(1)}MB`
    );
  }
  return result;
}

async function loadAggregations(): Promise<Aggregations> {
  // Parallel read of all 18 aggregation files. The two largest
  // (by-prescriber 5.9MB, by-pharmacy 4.2MB) dominate wall time if run
  // sequentially; parallel brings total close to max(individual times).
  const [
    overview,
    cycles,
    by_client,
    by_nrid,
    by_chain,
    by_pharmacy,
    by_ndc,
    by_prescriber,
    by_member,
    top_pharmacies,
    top_ndcs,
    top_clients,
    daily_volume,
    nrid_distribution,
    reversal_rate,
    activity_feed,
    investigations,
    manifest,
  ] = await Promise.all([
    readJson<Aggregations["overview"]>("overview.json"),
    readJson<Aggregations["cycles"]>("cycles.json"),
    readJson<Aggregations["by_client"]>("by-client.json"),
    readJson<Aggregations["by_nrid"]>("by-nrid.json"),
    readJson<Aggregations["by_chain"]>("by-chain.json"),
    readJson<Aggregations["by_pharmacy"]>("by-pharmacy.json"),
    readJson<Aggregations["by_ndc"]>("by-ndc.json"),
    readJson<Aggregations["by_prescriber"]>("by-prescriber.json"),
    readJson<Aggregations["by_member"]>("by-member.json"),
    readJson<Aggregations["top_pharmacies"]>("top-pharmacies.json"),
    readJson<Aggregations["top_ndcs"]>("top-ndcs.json"),
    readJson<Aggregations["top_clients"]>("top-clients.json"),
    readJson<Aggregations["daily_volume"]>("daily-volume.json"),
    readJson<Aggregations["nrid_distribution"]>("nrid-distribution.json"),
    readJson<Aggregations["reversal_rate"]>("reversal-rate.json"),
    readJson<Aggregations["activity_feed"]>("activity-feed.json"),
    readJson<Aggregations["investigations"]>("investigations.json"),
    readJson<Aggregations["manifest"]>("manifest.json"),
  ]);

  return {
    overview,
    cycles,
    by_client,
    by_nrid,
    by_chain,
    by_pharmacy,
    by_ndc,
    by_prescriber,
    by_member,
    top_pharmacies,
    top_ndcs,
    top_clients,
    daily_volume,
    nrid_distribution,
    reversal_rate,
    activity_feed,
    investigations,
    manifest,
  };
}

async function loadClaimFiles(
  groupMap: Map<string, string>
): Promise<ParsedClaim[]> {
  const FILES = [
    { name: "InfinityRX_20260401_1618.txt", cycleId: "BC-2026-SM-08", hasHeader: true },
    { name: "InfinityRX_20260401_0815.txt", cycleId: "BC-2026-SM-07", hasHeader: false },
    { name: "InfinityRX_20260316_0815.txt", cycleId: "BC-2026-SM-06", hasHeader: false },
  ];

  // Parallel I/O. The `text` local goes out of scope after parsing completes,
  // so the 10–15MB raw strings can be garbage-collected before the next
  // iteration allocates — peak memory stays bounded by the largest file.
  const perFile = await Promise.all(
    FILES.map(async (f) => {
      const readStart = Date.now();
      const text = await fs.readFile(path.join(SOURCE_DIR, f.name), "utf-8");
      const readMs = Date.now() - readStart;
      const parseStart = Date.now();
      const parsed = parseFile(text, {
        hasHeader: f.hasHeader,
        headers: [],
        groupMap,
        cycleId: f.cycleId,
      });
      const parseMs = Date.now() - parseStart;
      console.log(
        `[store] ${f.name}: read ${readMs}ms, parse ${parseMs}ms, ${parsed.length.toLocaleString()} claims`
      );
      return parsed;
    })
  );

  return perFile.flat();
}

async function initializeStore(): Promise<Store> {
  const totalStart = Date.now();
  console.log("[store] initializing…");

  // Aggregations and claims are independent. Launch both in parallel.
  // Inside the claims branch, buildGroupMap must complete before parsing
  // can start (parseFile needs the groupMap), but runs concurrently with
  // the aggregation reads.
  const [claims, aggregations] = await Promise.all([
    (async () => {
      const groupMap = await buildGroupMap();
      return loadClaimFiles(groupMap);
    })(),
    loadAggregations(),
  ]);

  const totalMs = Date.now() - totalStart;
  console.log(
    `[store] ready in ${totalMs}ms — ${claims.length.toLocaleString()} claims, 18 aggregations`
  );
  return { claims, aggregations };
}

function getStore(): Promise<Store> {
  if (!_storePromise) {
    _storePromise = initializeStore().catch((err) => {
      // Clear the cached promise on failure so the next caller can retry
      // with a fresh initialization instead of being stuck on a rejected promise.
      _storePromise = null;
      throw err;
    });
  }
  return _storePromise;
}

export async function getClaims(): Promise<ParsedClaim[]> {
  const store = await getStore();
  return store.claims;
}

export async function getAggregations(): Promise<Aggregations> {
  const store = await getStore();
  return store.aggregations;
}
