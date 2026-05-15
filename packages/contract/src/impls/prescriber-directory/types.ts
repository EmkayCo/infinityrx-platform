import { z } from "zod";

/** NPI: 10-digit Luhn-valid number. Validation deferred to backend; client accepts string. */
export const NpiSchema = z.string().regex(/^\d{10}$/);
export type Npi = z.infer<typeof NpiSchema>;

export const PrescriberSchema = z.object({
  npi: NpiSchema,
  first_name: z.string(),
  last_name: z.string(),
  credential: z.string().optional(),
  primary_specialty: z.string(),
  state: z.string().length(2),
  zip: z.string().regex(/^\d{5}(-\d{4})?$/),
  active: z.boolean(),
});
export type Prescriber = z.infer<typeof PrescriberSchema>;

export const PrescriberSearchRequestSchema = z.object({
  q: z.string().min(1).max(64),
  state: z.string().length(2).optional(),
  specialty: z.string().optional(),
  limit: z.number().int().positive().max(100).default(20),
  cursor: z.string().optional(),
});
export type PrescriberSearchRequest = z.infer<typeof PrescriberSearchRequestSchema>;

export const PrescriberSearchResponseSchema = z.object({
  results: z.array(PrescriberSchema),
  next_cursor: z.string().optional(),
  total: z.number().int().nonnegative(),
});
export type PrescriberSearchResponse = z.infer<typeof PrescriberSearchResponseSchema>;
