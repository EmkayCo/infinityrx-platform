// packages/modules/paysync/src/inbox/useInboxItems.ts
// TanStack Query hook per §10.5 resolved spec.
// staleTime 10s + refetchOnWindowFocus; no WebSocket in SP-1.
// BFF route in src/bff/inbox.ts; real backend wiring lands in Plan B.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import type { InboxItem, RbacRole } from "./types.js";

export type UseInboxItemsResult = UseQueryResult<InboxItem[], Error>;

export function useInboxItems(role: RbacRole): UseInboxItemsResult {
  return useQuery({
    queryKey: ["paysync", "inbox", role] as const,
    queryFn: async () => {
      const res = await fetch(`/api/paysync/inbox?role=${encodeURIComponent(role)}`);
      if (!res.ok) {
        throw new Error(`inbox fetch failed: ${res.status} ${res.statusText}`);
      }
      return (await res.json()) as InboxItem[];
    },
    staleTime: 10_000,
    refetchOnWindowFocus: true,
  });
}
