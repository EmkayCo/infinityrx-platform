// packages/contract/src/impls/paysync/types.ts
// Zod schemas + types for the paysync contract surface (UploadsClient,
// InboxClient). Mirrors the prescriber-directory pattern: schemas are the
// runtime validators, types are the inferred TS shapes.

import { z } from "zod";

// ── RBAC role (mirrors the module-side type but lives in the contract so
// backend clients can speak in the same vocabulary as the UI) ────────────
export const RbacRoleSchema = z.enum(["operator", "approver", "auditor"]);
export type RbacRole = z.infer<typeof RbacRoleSchema>;

// ── Upload (paysync.upload backend resource — Plan B creates it) ────────
export const UploadStatusSchema = z.enum([
  "received",
  "parsing",
  "validated",
  "rejected",
  "applied",
]);
export type UploadStatus = z.infer<typeof UploadStatusSchema>;

export const UploadSchema = z.object({
  id: z.string().uuid(),
  tenant_id: z.string().uuid(),
  filename: z.string().min(1).max(255),
  // SHA-256 hex of the canonical bytes — content-addressed dedupe key.
  content_sha256: z.string().regex(/^[a-f0-9]{64}$/),
  status: UploadStatusSchema,
  // Decimal as string per .claude/rules/financial-precision.md. Aggregate
  // amount across all claims in this upload; null until parsing completes.
  total_billed_amount: z.string().nullable(),
  claim_count: z.number().int().nonnegative(),
  row_error_count: z.number().int().nonnegative(),
  uploaded_by_user_id: z.string().uuid(),
  uploaded_at: z.string().datetime({ offset: true }),
});
export type Upload = z.infer<typeof UploadSchema>;

// Inbox item from the contract perspective — alias renamed in the contract
// barrel export to avoid clashing with the module's own InboxItem type.
export const InboxItemSchema = z.object({
  id: z.string(),
  kind: z.string(),
  tenant_id: z.string(),
  upload_id: z.string().nullable(),
  rbac_required: RbacRoleSchema,
  created_at: z.string().datetime({ offset: true }),
  priority: z.enum(["normal", "high"]),
  payload: z.record(z.string(), z.unknown()),
});
export type InboxItem = z.infer<typeof InboxItemSchema>;

// Paginated upload list response.
export const UploadListResponseSchema = z.object({
  results: z.array(UploadSchema),
  next_cursor: z.string().optional(),
  total: z.number().int().nonnegative(),
});
export type UploadListResponse = z.infer<typeof UploadListResponseSchema>;

// List query.
export const UploadListRequestSchema = z.object({
  status: UploadStatusSchema.optional(),
  limit: z.number().int().positive().max(200).default(50),
  cursor: z.string().optional(),
});
export type UploadListRequest = z.infer<typeof UploadListRequestSchema>;
