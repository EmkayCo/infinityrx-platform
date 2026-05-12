"use client";

// Server-side paginated table — Wave 40 M1.
//
// Reusable across paysync list pages. Caller owns data fetching;
// this component owns pagination UI + sort indicators + loading
// states. Page state is URL-synced via Next router so deep links
// preserve filter/sort/page.

import { useCallback } from "react";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import {
  ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight,
  ArrowUpDown, ArrowUp, ArrowDown, Loader2,
} from "lucide-react";
import { cn } from "@shared/lib/format";

export interface PaginatedColumn<T> {
  id: string;
  header: string;
  accessor: (row: T) => React.ReactNode;
  sortKey?: string;
  align?: "left" | "right" | "center";
  width?: string;
  className?: string;
}

export interface PaginatedTableProps<T> {
  columns: PaginatedColumn<T>[];
  rows: T[];
  total: number;
  page: number;
  pageSize: number;
  loading?: boolean;
  error?: string | null;
  rowKey: (row: T) => string;
  onRowClick?: (row: T) => void;
  emptyTitle?: string;
  emptyHint?: string;
  emptyAction?: React.ReactNode;
  pageSizeOptions?: number[];
}

export function PaginatedTable<T>({
  columns, rows, total, page, pageSize,
  loading, error, rowKey, onRowClick,
  emptyTitle = "No results",
  emptyHint, emptyAction,
  pageSizeOptions = [25, 50, 100, 200],
}: PaginatedTableProps<T>) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  const setParam = useCallback((updates: Record<string, string | null>) => {
    const next = new URLSearchParams(params.toString());
    for (const [k, v] of Object.entries(updates)) {
      if (v === null || v === "") next.delete(k);
      else next.set(k, v);
    }
    router.push(`${pathname}?${next.toString()}`);
  }, [router, pathname, params]);

  const sortBy = params.get("sort_by") ?? "";
  const sortDir = (params.get("sort_dir") as "asc" | "desc") ?? "desc";

  const handleSort = useCallback((column: PaginatedColumn<T>) => {
    if (!column.sortKey) return;
    if (sortBy === column.sortKey) {
      setParam({ sort_dir: sortDir === "asc" ? "desc" : "asc", page: "1" });
    } else {
      setParam({ sort_by: column.sortKey, sort_dir: "asc", page: "1" });
    }
  }, [sortBy, sortDir, setParam]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(total, page * pageSize);

  return (
    <div className="rounded-lg border bg-card">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-muted/30 text-xs uppercase tracking-wider text-muted-foreground">
            <tr>
              {columns.map((c) => {
                const isSorted = sortBy === c.sortKey;
                const Icon = !c.sortKey ? null
                  : !isSorted ? ArrowUpDown
                  : sortDir === "asc" ? ArrowUp : ArrowDown;
                return (
                  <th
                    key={c.id}
                    className={cn(
                      "px-4 py-2 font-medium",
                      c.align === "right" ? "text-right" :
                      c.align === "center" ? "text-center" : "text-left",
                      c.sortKey && "cursor-pointer select-none hover:text-foreground",
                      c.className,
                    )}
                    style={c.width ? { width: c.width } : undefined}
                    onClick={() => handleSort(c)}
                    role={c.sortKey ? "button" : undefined}
                    aria-sort={
                      !c.sortKey ? undefined :
                      !isSorted ? "none" :
                      sortDir === "asc" ? "ascending" : "descending"
                    }
                  >
                    <span className="inline-flex items-center gap-1">
                      {c.header}
                      {Icon && <Icon className="h-3 w-3" aria-hidden="true" />}
                    </span>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody className="divide-y">
            {loading && rows.length === 0 && (
              <tr>
                <td colSpan={columns.length} className="px-4 py-12 text-center">
                  <span className="inline-flex items-center gap-2 text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Loading…
                  </span>
                </td>
              </tr>
            )}
            {!loading && error && (
              <tr>
                <td colSpan={columns.length}
                    className="px-4 py-12 text-center text-rose-500">
                  {error}
                </td>
              </tr>
            )}
            {!loading && !error && rows.length === 0 && (
              <tr>
                <td colSpan={columns.length} className="px-4 py-12 text-center">
                  <p className="font-medium">{emptyTitle}</p>
                  {emptyHint && (
                    <p className="mt-1 text-xs text-muted-foreground">
                      {emptyHint}
                    </p>
                  )}
                  {emptyAction && <div className="mt-4">{emptyAction}</div>}
                </td>
              </tr>
            )}
            {rows.map((row) => (
              <tr
                key={rowKey(row)}
                className={cn(
                  onRowClick && "cursor-pointer hover:bg-muted/30",
                )}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
              >
                {columns.map((c) => (
                  <td
                    key={c.id}
                    className={cn(
                      "px-4 py-2",
                      c.align === "right" ? "text-right tabular-nums" :
                      c.align === "center" ? "text-center" : "text-left",
                      c.className,
                    )}
                  >
                    {c.accessor(row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t px-4 py-2 text-xs">
        <div className="text-muted-foreground">
          {total === 0 ? "0 of 0" : `${from}–${to} of ${total.toLocaleString()}`}
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-1.5">
            <span className="text-muted-foreground">Rows</span>
            <select
              value={pageSize}
              onChange={(e) => setParam({
                page_size: e.target.value, page: "1",
              })}
              className="rounded-md border bg-background px-2 py-1 text-xs"
            >
              {pageSizeOptions.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </label>
          <div className="flex items-center gap-1">
            <PageButton
              disabled={page === 1}
              onClick={() => setParam({ page: "1" })}
              ariaLabel="First page"
            >
              <ChevronsLeft className="h-3.5 w-3.5" />
            </PageButton>
            <PageButton
              disabled={page === 1}
              onClick={() => setParam({ page: String(page - 1) })}
              ariaLabel="Previous page"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
            </PageButton>
            <span className="px-2 tabular-nums">
              {page} / {totalPages}
            </span>
            <PageButton
              disabled={page >= totalPages}
              onClick={() => setParam({ page: String(page + 1) })}
              ariaLabel="Next page"
            >
              <ChevronRight className="h-3.5 w-3.5" />
            </PageButton>
            <PageButton
              disabled={page >= totalPages}
              onClick={() => setParam({ page: String(totalPages) })}
              ariaLabel="Last page"
            >
              <ChevronsRight className="h-3.5 w-3.5" />
            </PageButton>
          </div>
        </div>
      </div>
    </div>
  );
}

function PageButton({
  children, disabled, onClick, ariaLabel,
}: {
  children: React.ReactNode;
  disabled: boolean;
  onClick: () => void;
  ariaLabel: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={ariaLabel}
      className={cn(
        "rounded-md border bg-background p-1",
        disabled
          ? "cursor-not-allowed opacity-40"
          : "hover:bg-muted",
      )}
    >
      {children}
    </button>
  );
}

export function readPaginationFromUrl(
  params: URLSearchParams,
  defaults: { page?: number; page_size?: number; sort_by?: string; sort_dir?: "asc" | "desc" } = {},
) {
  return {
    page: Number(params.get("page") ?? defaults.page ?? 1),
    page_size: Number(params.get("page_size") ?? defaults.page_size ?? 50),
    sort_by: params.get("sort_by") ?? defaults.sort_by,
    sort_dir: (params.get("sort_dir") as "asc" | "desc") ?? defaults.sort_dir ?? "desc",
  };
}
