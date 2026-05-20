import { z } from "zod";

/**
 * Canonical error envelope per `.claude/rules/error-handling.md`:
 *   { error: { code, message, field?, correlation_id, details? } }
 *
 * `details` carries code-specific recovery context (e.g. DUPLICATE_UPLOAD ships
 * existing_upload_id under details). Every backend returns errors in this shape.
 * Every BFF wraps thrown errors in this shape. The zod schema is the authority
 * -- runtime validation at every boundary.
 */
export const ErrorEnvelopeSchema = z.object({
  error: z.object({
    code: z.string().min(1, "error.code must not be empty"),
    message: z.string(),
    field: z.string().optional(),
    correlation_id: z.string().uuid(),
    details: z.record(z.unknown()).optional(),
  }),
});

export type ErrorEnvelope = z.infer<typeof ErrorEnvelopeSchema>;

export function isErrorEnvelope(candidate: unknown): candidate is ErrorEnvelope {
  return ErrorEnvelopeSchema.safeParse(candidate).success;
}
