import { z } from "zod";

/**
 * Declarative per-resource cache policy. Consumed by the BFF cache adapter (Plan C)
 * and by the contract clients to emit invalidation tags on mutations.
 *
 * - `ttl_seconds`: positive int (seconds)
 * - `key`: ordered segments; concrete cache key is segments joined + interpolated args
 * - `invalidation_tags`: tags this resource belongs to; mutations emit these to purge
 * - `backend_down`: behavior when the backend is unreachable
 */
export const CachePolicySchema = z.object({
  ttl_seconds: z.number().int().positive(),
  key: z.array(z.string().min(1)),
  invalidation_tags: z.array(z.string().min(1)),
  backend_down: z.enum(["stale-ok", "fail-fast", "fall-back-to-mock"]),
});

export type CachePolicy = z.infer<typeof CachePolicySchema>;
