// SP-2 Plan C: page wrapper.
// Logic in @infinityrx/module-directories — PricingPage.
//
// Client component so we can read the NextAuth session token and fetch
// ingestion status to populate the pricing FreshnessChips.
"use client";

import { useSession } from "next-auth/react";
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { PricingPage } from "@infinityrx/module-directories";

interface SourceStatus {
  source: string;
  last_run: { started_at: string } | null;
}

export default function Page() {
  const { data: session, status } = useSession();
  const token = (session as unknown as { access_token?: string } | null)
    ?.access_token;

  const authReady = status !== "loading";

  const authFetch: typeof fetch = useMemo(() => {
    if (!token) return fetch;
    return (input, init) =>
      fetch(input, {
        ...init,
        headers: {
          ...(init?.headers as Record<string, string> | undefined),
          Authorization: `Bearer ${token}`,
        },
      });
  }, [token]);

  const { data: statuses = [] } = useQuery<SourceStatus[]>({
    queryKey: ["ingestion-status"],
    queryFn: async () => {
      const resp = await authFetch("/api/directories/ingest/status");
      if (!resp.ok) return [];
      return resp.json();
    },
    enabled: authReady && Boolean(token),
    staleTime: 5 * 60_000,
  });

  const bySource = Object.fromEntries(statuses.map((s) => [s.source, s]));

  return (
    <PricingPage
      cms_asp_last_run_at={bySource["cms_asp"]?.last_run?.started_at ?? null}
      cms_nadac_last_run_at={bySource["cms_nadac"]?.last_run?.started_at ?? null}
    />
  );
}
