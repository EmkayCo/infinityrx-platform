// SP-2 Plan C: page wrapper.
// Logic in @infinityrx/module-directories — PharmaciesListPage.
//
// Client component so we can read the NextAuth session token and fetch
// ingestion status to populate the ncpdp FreshnessChip.
"use client";

import { useSession } from "next-auth/react";
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { PharmaciesListPage } from "@infinityrx/module-directories";

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
  const ncpdp_last_run_at = bySource["ncpdp"]?.last_run?.started_at ?? null;

  return <PharmaciesListPage ncpdp_last_run_at={ncpdp_last_run_at} />;
}
