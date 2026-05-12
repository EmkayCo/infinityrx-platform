"use client";

// Global search for paysync entities — Wave 40 M5.
//
// Header search box that issues a query against the paysync search
// endpoint and renders results grouped by entity type. Each result
// links to the appropriate entity detail page.

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";
import { ApiClientError } from "@shared/lib/api-client";
import { paysyncSearch, type SearchResult } from "@shared/lib/paysync-api";

export function GlobalSearch() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [busy, setBusy] = useState(false);

  // Cmd/Ctrl-K opens search.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen(true);
      }
      if (e.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (open && inputRef.current) inputRef.current.focus();
  }, [open]);

  // Debounced search.
  useEffect(() => {
    if (!query.trim() || query.trim().length < 2) {
      setResults([]);
      return;
    }
    const handle = setTimeout(async () => {
      setBusy(true);
      try {
        const res = await paysyncSearch(query.trim());
        setResults(res);
      } catch (e) {
        if (!(e instanceof ApiClientError)) throw e;
        // search failures are silent — no result list is harmless
        setResults([]);
      } finally { setBusy(false); }
    }, 250);
    return () => clearTimeout(handle);
  }, [query]);

  function navigate(url: string) {
    setOpen(false);
    setQuery("");
    setResults([]);
    router.push(url);
  }

  if (!open) {
    return (
      <button onClick={() => setOpen(true)}
              aria-label="Open global search (⌘K)"
              className="inline-flex items-center gap-2 rounded-md border bg-background px-3 py-1.5 text-xs text-muted-foreground hover:bg-muted">
        <Search className="h-3.5 w-3.5" />
        <span>Search</span>
        <kbd className="rounded border bg-muted/50 px-1 text-[10px] font-mono">⌘K</kbd>
      </button>
    );
  }

  const groups = results.reduce<Record<string, SearchResult[]>>((acc, r) => {
    (acc[r.type] ??= []).push(r); return acc;
  }, {});

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-background/80 backdrop-blur-sm p-4 pt-24"
         onClick={() => setOpen(false)}>
      <div className="w-full max-w-xl rounded-lg border bg-card shadow-lg"
           onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2 border-b px-3">
          <Search className="h-4 w-4 text-muted-foreground" />
          <input
            ref={inputRef} type="text"
            placeholder="Search invoice #, batch #, NPI, auth #, pay-to..."
            value={query} onChange={(e) => setQuery(e.target.value)}
            className="flex-1 bg-transparent py-3 text-sm outline-none"
          />
          {busy && <span className="text-[11px] text-muted-foreground">searching…</span>}
          <kbd className="rounded border bg-muted/50 px-1 text-[10px] font-mono">esc</kbd>
        </div>

        <div className="max-h-[60vh] overflow-y-auto p-2">
          {query.trim().length < 2
            ? <p className="p-4 text-center text-xs text-muted-foreground">
                Type at least 2 characters to search.
              </p>
            : Object.keys(groups).length === 0 && !busy
            ? <p className="p-4 text-center text-xs text-muted-foreground">
                No results.
              </p>
            : Object.entries(groups).map(([type, group]) => (
              <section key={type} className="mb-2">
                <p className="px-2 py-1 text-[10px] uppercase tracking-wider text-muted-foreground">
                  {type.replace(/_/g, " ")}
                </p>
                <ul>
                  {group.map((r) => (
                    <li key={r.id}>
                      <button onClick={() => navigate(r.url)}
                              className="w-full rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted/50">
                        <p>{r.label}</p>
                        {r.sublabel && (
                          <p className="text-xs text-muted-foreground">{r.sublabel}</p>
                        )}
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
        </div>
      </div>
    </div>
  );
}
