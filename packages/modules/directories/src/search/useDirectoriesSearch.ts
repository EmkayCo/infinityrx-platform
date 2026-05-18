// src/search/useDirectoriesSearch.ts
// Client-side TanStack Query hook for federated directory search.
// Debounce (80ms) is handled by the caller (CommandPalette uses setTimeout).
import { useQuery } from "@tanstack/react-query";
import { SearchResponseSchema, type SearchResponse } from "./schemas.js";

export interface UseDirectoriesSearchOpts {
  datasets?: "all" | string[];
  limit?: number;
  enabled?: boolean;
}

export interface UseDirectoriesSearchResult {
  results: SearchResponse["results"];
  isPartial: boolean;
  timedOutDatasets: SearchResponse["timed_out_datasets"];
  isLoading: boolean;
  error: Error | null;
}

async function fetchSearch(q: string, opts: UseDirectoriesSearchOpts): Promise<SearchResponse> {
  const params = new URLSearchParams({ q, limit: String(opts.limit ?? 20) });
  const res = await fetch(`/api/directories/search?${params.toString()}`);
  if (!res.ok) throw new Error(`Search failed: ${res.status}`);
  const data = await res.json();
  return SearchResponseSchema.parse(data);
}

export function useDirectoriesSearch(
  query: string,
  opts: UseDirectoriesSearchOpts = {},
): UseDirectoriesSearchResult {
  const trimmed = query.trim();
  const { data, isLoading, error } = useQuery({
    queryKey: ["dir:search", trimmed, opts.datasets, opts.limit],
    queryFn: () => fetchSearch(trimmed, opts),
    enabled: (opts.enabled ?? true) && trimmed.length >= 2,
    staleTime: 30_000,
    gcTime: 60_000,
  });

  return {
    results: data?.results ?? [],
    isPartial: data?.is_partial ?? false,
    timedOutDatasets: data?.timed_out_datasets ?? [],
    isLoading,
    error: error as Error | null,
  };
}
