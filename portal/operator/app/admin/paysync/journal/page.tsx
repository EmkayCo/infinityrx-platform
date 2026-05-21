"use client";
/**
 * /admin/paysync/journal -- Paysync journal entries list + hash-chain verify.
 * Fetches via TanStack Query from /api/paysync/journal (BFF).
 * Renders JournalListPage + HashChainVerifyButton from @infinityrx/module-paysync.
 * Cache-Control: no-store enforced on BFF — financial audit hash-chain.
 */
import { useQuery } from "@tanstack/react-query";
import { JournalListPage, HashChainVerifyButton } from "@infinityrx/module-paysync";
import type { JournalEntry, JournalEntryListResponse, HashChainVerifyResponse } from "@infinityrx/contract";

async function fetchJournal(): Promise<JournalEntryListResponse> {
  const res = await fetch("/api/paysync/journal", { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch journal");
  return res.json() as Promise<JournalEntryListResponse>;
}

async function verifyChain(): Promise<HashChainVerifyResponse> {
  const res = await fetch("/api/paysync/journal/verify-chain", {
    method: "POST",
    cache: "no-store",
  });
  if (!res.ok) throw new Error("Chain verification failed");
  return res.json() as Promise<HashChainVerifyResponse>;
}

export default function JournalPage() {
  const { data, isLoading, error } = useQuery<JournalEntryListResponse, Error>({
    queryKey: ["paysync", "journal"],
    queryFn: fetchJournal,
    staleTime: 15_000,
  });

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Journal Entries</h1>
        <HashChainVerifyButton currentRole="operator" onVerify={verifyChain} />
      </div>
      <JournalListPage
        entries={(data?.results ?? []) as ReadonlyArray<JournalEntry>}
        isLoading={isLoading}
        error={error?.message ?? null}
      />
    </div>
  );
}
