/**
 * Next.js instrumentation hook — runs once on server start.
 *
 * We use it to warm up the in-memory claims store so the first user request
 * to /api/claims or /billing/claims doesn't pay the ~700ms cold init cost
 * on top of route compilation.
 */
export async function register() {
  if (process.env.NEXT_RUNTIME !== "nodejs") return;

  try {
    // Fire and forget — we don't block server start on store init, we just
    // nudge the lazy singleton so it begins loading in parallel with any
    // incoming requests. Subsequent callers of getClaims/getAggregations
    // hit the same cached promise.
    const { getClaims } = await import("@/lib/data/store");
    getClaims()
      .then((claims) =>
        console.log(`[warmup] claims store ready (${claims.length.toLocaleString()} claims)`)
      )
      .catch((err) =>
        console.error("[warmup] claims store init failed:", err)
      );
  } catch (err) {
    console.error("[warmup] register failed:", err);
  }
}
