// src/search/schemas.ts
// Zod schemas for the federated search spine (SP-2 Plan A).
import { z } from "zod";

/**
 * Dataset cluster keys — 18 PRIMARY browse-cluster source keys.
 *
 * IMPORTANT: This enum intentionally contains 18 keys, not 20.
 * `nppes_monthly` and `nppes_deactivation` are scheduler sub-modes of `nppes`
 * (separate cron schedules for the same NPPES browse cluster). They appear in
 * TRIGGERABLE_SOURCES (Plan C) for ingestion triggering but are NOT separate
 * browse surfaces — they share the Prescribers cluster with `nppes`.
 * Search results and browse cluster items only use these 18 keys.
 *
 * TRIGGERABLE_SOURCES (Plan C) has 20 keys = these 18 + nppes_monthly + nppes_deactivation.
 * That is correct and intentional — ingestion can be triggered per sub-mode,
 * but search results always carry the parent source key ("nppes").
 */
export const DatasetKeySchema = z.enum([
  "nppes",
  "ncpdp",
  "fda_ndc",
  "fda_orange_book",
  "fda_purple_book",
  "fda_drug_shortages",
  "fda_rems",
  "rxnorm",
  "hcpcs",
  "icd10_cm",
  "cms_asp",
  "cms_nadac",
  "state_medicaid_bins",
  "cms_opt_out",
  "ofac_sdn",
  "sam_exclusions",
  "oig_leie",
  "dea_registrations",
]);
export type DatasetKey = z.infer<typeof DatasetKeySchema>;

/** Single federated search result (BFF boundary + client boundary validated) */
export const SearchResultRecordSchema = z.object({
  dataset: DatasetKeySchema,
  id: z.string().min(1),
  display: z.string().min(1),
  secondary: z.string().default(""),
  source_date: z.string().nullable(),
  run_id: z.string().nullable(),
  b9_blocked: z.boolean().optional(),
});
export type SearchResultRecord = z.infer<typeof SearchResultRecordSchema>;

/** BFF response envelope */
export const SearchResponseSchema = z.object({
  results: z.array(SearchResultRecordSchema),
  is_partial: z.boolean(),
  timed_out_datasets: z.array(DatasetKeySchema),
});
export type SearchResponse = z.infer<typeof SearchResponseSchema>;

/** ID pattern detection — NPI, NDC, HCPCS, ICD-10 */
export const ID_PATTERNS = {
  NPI: /^\d{10}$/,
  NDC_11: /^\d{11}$/,
  NDC_HYPHENATED: /^\d{4,5}-\d{3,4}-\d{1,2}$/,
  HCPCS: /^[A-Z]\d{4}$/i,
  ICD10: /^[A-Z]\d{2}(\.\w{1,4})?$/i,
} as const;
