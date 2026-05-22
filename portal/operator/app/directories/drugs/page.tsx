// SP-2 Plan C: page wrapper.
// Logic in @infinityrx/module-directories — DrugsListPage.
//
// Client component so we can read the NextAuth session token and fetch
// ingestion status to populate the fda_ndc FreshnessChip.
"use client";

import { useSession } from "next-auth/react";
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { DrugsListPage } from "@infinityrx/module-directories";

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
  const fda_ndc_last_run_at = bySource["fda_ndc"]?.last_run?.started_at ?? null;

  return <DrugsListPage fda_ndc_last_run_at={fda_ndc_last_run_at} />;
}
