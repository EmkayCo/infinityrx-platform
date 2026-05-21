"use client";
/**
 * /admin/paysync/journal/[id] -- Single journal entry detail.
 * Fetches via TanStack Query from /api/paysync/journal/[id] (BFF).
 * Renders JournalDetailPage from @infinityrx/module-paysync.
 */
import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { JournalDetailPage } from "@infinityrx/module-paysync";
import type { JournalEntry } from "@infinityrx/contract";

async function fetchJournalEntry(id: string): Promise<JournalEntry | null> {
  const res = await fetch(`/api/paysync/journal/${encodeURIComponent(id)}`, {
    cache: "no-store",
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error("Failed to fetch journal entry");
  return res.json() as Promise<JournalEntry>;
}

export default function JournalDetailRoute() {
  const params = useParams<{ id: string }>();
  const id = params.id ?? "";

  const { data, isLoading, error } = useQuery<JournalEntry | null, Error>({
    queryKey: ["paysync", "journal", id],
    queryFn: () => fetchJournalEntry(id),
    enabled: !!id,
    staleTime: 15_000,
  });

  return (
    <div className="space-y-6 p-6">
      <JournalDetailPage
        entry={data ?? null}
        isLoading={isLoading}
        error={error?.message ?? null}
      />
    </div>
  );
}
