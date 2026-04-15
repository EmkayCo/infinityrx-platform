"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  Columns3,
  Download,
  Search,
  X,
} from "lucide-react";
import { cn } from "@shared/lib/format";
import { formatValue, type ValueFormat } from "./format-value";
import { StatusBadge } from "./status-badge";

export interface Column<T> {
  id: string;
  header: string;
  accessor: (row: T) => unknown;
  format?: ValueFormat;
  sortable?: boolean;
  defaultVisible?: boolean;
  pinned?: boolean;
  width?: number;
  cell?: (value: unknown, row: T) => React.ReactNode;
  align?: "left" | "right" | "center";
}

export interface BulkAction {
  id: string;
  label: string;
  variant?: "default" | "destructive";
}

interface Pagination {
  pageSize: number;
  pageSizeOptions?: number[];
}

export interface ConfigurableDataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  tableId: string;
  onRowClick?: (row: T) => void;
  getRowId?: (row: T, index: number) => string;
  searchable?: boolean;
  exportable?: boolean;
  selectable?: boolean;
  onBulkAction?: (actionId: string, selectedRows: T[]) => void;
  bulkActions?: BulkAction[];
  emptyMessage?: string;
  loading?: boolean;
  pagination?: Pagination;
  className?: string;
}

interface TablePrefs {
  visible: string[];
  order: string[];
}

const PREFS_KEY_PREFIX = "ifx-table-prefs:";

function readPrefs(tableId: string): TablePrefs | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(PREFS_KEY_PREFIX + tableId);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed.visible) && Array.isArray(parsed.order)) return parsed;
  } catch {
    // ignore
  }
  return null;
}

function writePrefs(tableId: string, prefs: TablePrefs) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(PREFS_KEY_PREFIX + tableId, JSON.stringify(prefs));
  } catch {
    // ignore
  }
}

function alignClass(align?: Column<unknown>["align"]): string {
  if (align === "right") return "text-right";
  if (align === "center") return "text-center";
  return "text-left";
}

function defaultCell<T>(col: Column<T>, value: unknown, row: T): React.ReactNode {
  if (col.cell) return col.cell(value, row);
  if (value === null || value === undefined || value === "") {
    return <span className="text-ifx-gray-400">—</span>;
  }
  if (col.format === "status") {
    return <StatusBadge status={String(value)} />;
  }
  if (col.format === "npi" || col.format === "ndc") {
    return <span className="font-mono text-[13px]">{formatValue(value, col.format)}</span>;
  }
  if (col.format) {
    return formatValue(value, col.format);
  }
  return String(value);
}

export function ConfigurableDataTable<T>({
  columns,
  data,
  tableId,
  onRowClick,
  getRowId = (_row, i) => String(i),
  searchable = true,
  exportable = true,
  selectable = false,
  onBulkAction,
  bulkActions,
  emptyMessage = "No records found.",
  loading = false,
  pagination,
  className,
}: ConfigurableDataTableProps<T>) {
  // --- Column visibility & order (persisted) ---
  const defaultVisible = useMemo(
    () => columns.filter((c) => c.defaultVisible !== false).map((c) => c.id),
    [columns],
  );
  const defaultOrder = useMemo(() => columns.map((c) => c.id), [columns]);

  const [visibleIds, setVisibleIds] = useState<string[]>(defaultVisible);
  const [columnOrder, setColumnOrder] = useState<string[]>(defaultOrder);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    const prefs = readPrefs(tableId);
    if (prefs) {
      const colSet = new Set(columns.map((c) => c.id));
      setVisibleIds(prefs.visible.filter((id) => colSet.has(id)));
      const ordered = prefs.order.filter((id) => colSet.has(id));
      const missing = defaultOrder.filter((id) => !ordered.includes(id));
      setColumnOrder([...ordered, ...missing]);
    }
    setHydrated(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tableId]);

  const toggleColumn = useCallback(
    (id: string) => {
      setVisibleIds((prev) => {
        const next = prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id];
        writePrefs(tableId, { visible: next, order: columnOrder });
        return next;
      });
    },
    [tableId, columnOrder],
  );

  // --- Search ---
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setSearch(searchInput), 300);
    return () => clearTimeout(t);
  }, [searchInput]);

  // --- Sort ---
  const [sort, setSort] = useState<{ id: string; dir: "asc" | "desc" } | null>(null);
  const toggleSort = (id: string) => {
    setSort((prev) => {
      if (!prev || prev.id !== id) return { id, dir: "asc" };
      if (prev.dir === "asc") return { id, dir: "desc" };
      return null;
    });
  };

  // --- Selection ---
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const clearSelection = () => setSelected(new Set());

  // --- Pagination ---
  const pageSizeOptions = pagination?.pageSizeOptions ?? [25, 50, 100];
  const [pageSize, setPageSize] = useState(pagination?.pageSize ?? 25);
  const [page, setPage] = useState(0);
  useEffect(() => {
    setPage(0);
  }, [search, sort, data.length]);

  // --- Effective columns (ordered + visible) ---
  const orderedColumns = useMemo(() => {
    const colMap = new Map(columns.map((c) => [c.id, c]));
    return columnOrder
      .map((id) => colMap.get(id))
      .filter((c): c is Column<T> => !!c);
  }, [columns, columnOrder]);

  const visibleColumns = useMemo(() => {
    // Keep pinned columns always visible
    return orderedColumns.filter(
      (c) => c.pinned || visibleIds.includes(c.id),
    );
  }, [orderedColumns, visibleIds]);

  // --- Filter + sort ---
  const processedRows = useMemo(() => {
    let rows = data;

    if (search && searchable) {
      const q = search.toLowerCase();
      rows = rows.filter((row) =>
        visibleColumns.some((col) => {
          const val = col.accessor(row);
          if (val === null || val === undefined) return false;
          return String(val).toLowerCase().includes(q);
        }),
      );
    }

    if (sort) {
      const col = columns.find((c) => c.id === sort.id);
      if (col) {
        const dir = sort.dir === "asc" ? 1 : -1;
        rows = [...rows].sort((a, b) => {
          const av = col.accessor(a);
          const bv = col.accessor(b);
          if (av === bv) return 0;
          if (av === null || av === undefined) return 1;
          if (bv === null || bv === undefined) return -1;
          if (typeof av === "number" && typeof bv === "number") {
            return (av - bv) * dir;
          }
          return String(av).localeCompare(String(bv)) * dir;
        });
      }
    }

    return rows;
  }, [data, search, searchable, sort, columns, visibleColumns]);

  const totalRows = processedRows.length;
  const pageCount = Math.max(1, Math.ceil(totalRows / pageSize));
  const currentPage = Math.min(page, pageCount - 1);
  const pageRows = useMemo(
    () => processedRows.slice(currentPage * pageSize, (currentPage + 1) * pageSize),
    [processedRows, currentPage, pageSize],
  );

  // --- Selection helpers ---
  const pageRowIds = useMemo(
    () => pageRows.map((row, i) => getRowId(row, currentPage * pageSize + i)),
    [pageRows, getRowId, currentPage, pageSize],
  );
  const allPageSelected = pageRowIds.length > 0 && pageRowIds.every((id) => selected.has(id));
  const togglePageSelection = () => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (allPageSelected) {
        pageRowIds.forEach((id) => next.delete(id));
      } else {
        pageRowIds.forEach((id) => next.add(id));
      }
      return next;
    });
  };
  const toggleRowSelection = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const selectedRows = useMemo(() => {
    if (!selectable) return [];
    const map = new Map<string, T>();
    data.forEach((row, i) => {
      const id = getRowId(row, i);
      if (selected.has(id)) map.set(id, row);
    });
    return Array.from(map.values());
  }, [data, getRowId, selected, selectable]);

  // --- Column selector dropdown ---
  const [columnMenuOpen, setColumnMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!columnMenuOpen) return;
    function onClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setColumnMenuOpen(false);
      }
    }
    window.addEventListener("mousedown", onClick);
    return () => window.removeEventListener("mousedown", onClick);
  }, [columnMenuOpen]);

  // --- Export ---
  const handleExport = (fmt: "csv" | "excel") => {
    const headers = visibleColumns.map((c) => c.header);
    const rows = processedRows.map((row) =>
      visibleColumns.map((c) => {
        const raw = c.accessor(row);
        if (raw === null || raw === undefined) return "";
        if (c.format && c.format !== "text" && c.format !== "raw") {
          return formatValue(raw, c.format);
        }
        return String(raw);
      }),
    );
    exportToCsv(tableId, headers, rows, fmt === "excel" ? "xls" : "csv");
  };

  const [exportOpen, setExportOpen] = useState(false);
  const exportRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!exportOpen) return;
    function onClick(e: MouseEvent) {
      if (exportRef.current && !exportRef.current.contains(e.target as Node)) {
        setExportOpen(false);
      }
    }
    window.addEventListener("mousedown", onClick);
    return () => window.removeEventListener("mousedown", onClick);
  }, [exportOpen]);

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-2">
        {searchable && (
          <div className="relative flex-1 min-w-[200px] max-w-md">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-ifx-gray-400" />
            <input
              type="search"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search..."
              className={cn(
                "h-9 w-full rounded-md border border-ifx-gray-100 bg-white pl-9 pr-3 text-sm",
                "placeholder:text-ifx-gray-400",
                "focus:outline-none focus:ring-2 focus:ring-ifx-blue/40 focus:border-ifx-blue",
              )}
            />
          </div>
        )}

        <div className="flex items-center gap-2 ml-auto">
          {/* Column selector */}
          <div className="relative" ref={menuRef}>
            <button
              type="button"
              onClick={() => setColumnMenuOpen((o) => !o)}
              className="inline-flex items-center gap-1.5 rounded-md border border-ifx-gray-100 bg-white px-3 py-1.5 text-sm text-ifx-gray-700 hover:bg-ifx-gray-50"
            >
              <Columns3 className="h-4 w-4" />
              Columns
            </button>
            {columnMenuOpen && (
              <div className="absolute right-0 top-10 z-20 w-64 max-h-80 overflow-y-auto rounded-md border border-ifx-gray-100 bg-white shadow-lg p-1.5">
                <div className="px-2 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-ifx-gray-400">
                  Show columns
                </div>
                {orderedColumns.map((col) => {
                  const checked = col.pinned || visibleIds.includes(col.id);
                  return (
                    <label
                      key={col.id}
                      className={cn(
                        "flex items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-ifx-gray-50",
                        col.pinned && "opacity-60 cursor-not-allowed",
                      )}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        disabled={col.pinned}
                        onChange={() => toggleColumn(col.id)}
                        className="h-4 w-4 rounded border-ifx-gray-200 text-ifx-blue focus:ring-ifx-blue/40"
                      />
                      <span className="flex-1 text-ifx-gray-700">{col.header}</span>
                      {col.pinned && (
                        <span className="text-[10px] uppercase text-ifx-gray-400">Pinned</span>
                      )}
                    </label>
                  );
                })}
              </div>
            )}
          </div>

          {/* Export */}
          {exportable && (
            <div className="relative" ref={exportRef}>
              <button
                type="button"
                onClick={() => setExportOpen((o) => !o)}
                className="inline-flex items-center gap-1.5 rounded-md border border-ifx-gray-100 bg-white px-3 py-1.5 text-sm text-ifx-gray-700 hover:bg-ifx-gray-50"
              >
                <Download className="h-4 w-4" />
                Export
              </button>
              {exportOpen && (
                <div className="absolute right-0 top-10 z-20 w-36 rounded-md border border-ifx-gray-100 bg-white shadow-lg p-1">
                  <button
                    onClick={() => {
                      handleExport("csv");
                      setExportOpen(false);
                    }}
                    className="block w-full rounded-md px-3 py-1.5 text-left text-sm text-ifx-gray-700 hover:bg-ifx-gray-50"
                  >
                    CSV
                  </button>
                  <button
                    onClick={() => {
                      handleExport("excel");
                      setExportOpen(false);
                    }}
                    className="block w-full rounded-md px-3 py-1.5 text-left text-sm text-ifx-gray-700 hover:bg-ifx-gray-50"
                  >
                    Excel
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Bulk action bar */}
      {selectable && selected.size > 0 && bulkActions && bulkActions.length > 0 && (
        <div className="flex items-center gap-3 rounded-md border border-ifx-blue/30 bg-ifx-blue/5 px-3 py-2 text-sm">
          <span className="font-medium text-ifx-gray-900">
            {selected.size} selected
          </span>
          <div className="flex items-center gap-2">
            {bulkActions.map((action) => (
              <button
                key={action.id}
                onClick={() => onBulkAction?.(action.id, selectedRows)}
                className={cn(
                  "rounded-md border px-2.5 py-1 text-xs font-medium transition-colors",
                  action.variant === "destructive"
                    ? "border-ifx-error/30 bg-white text-ifx-error hover:bg-ifx-error-light"
                    : "border-ifx-gray-100 bg-white text-ifx-gray-700 hover:bg-ifx-gray-50",
                )}
              >
                {action.label}
              </button>
            ))}
          </div>
          <button
            onClick={clearSelection}
            className="ml-auto inline-flex items-center gap-1 text-xs text-ifx-gray-400 hover:text-ifx-gray-700"
          >
            <X className="h-3 w-3" /> Clear
          </button>
        </div>
      )}

      {/* Table */}
      <div className="relative overflow-auto rounded-lg border border-ifx-gray-100 bg-white ifx-card-shadow">
        <table className="w-full border-collapse text-sm">
          <thead className="sticky top-0 z-10 bg-ifx-gray-50">
            <tr>
              {selectable && (
                <th className="w-10 px-3 py-2 text-left">
                  <input
                    type="checkbox"
                    checked={allPageSelected}
                    onChange={togglePageSelection}
                    className="h-4 w-4 rounded border-ifx-gray-200 text-ifx-blue focus:ring-ifx-blue/40"
                    aria-label="Select all on page"
                  />
                </th>
              )}
              {visibleColumns.map((col) => {
                const isSorted = sort?.id === col.id;
                return (
                  <th
                    key={col.id}
                    style={col.width ? { width: col.width } : undefined}
                    className={cn(
                      "px-3 py-2 text-[12px] font-semibold uppercase tracking-wide text-ifx-gray-500 whitespace-nowrap",
                      alignClass(col.align),
                      col.pinned && "sticky left-0 z-10 bg-white",
                    )}
                  >
                    {col.sortable === false ? (
                      col.header
                    ) : (
                      <button
                        type="button"
                        onClick={() => toggleSort(col.id)}
                        className="inline-flex items-center gap-1 hover:text-ifx-gray-900"
                      >
                        {col.header}
                        {isSorted ? (
                          sort.dir === "asc" ? (
                            <ArrowUp className="h-3 w-3" />
                          ) : (
                            <ArrowDown className="h-3 w-3" />
                          )
                        ) : (
                          <ArrowUpDown className="h-3 w-3 opacity-40" />
                        )}
                      </button>
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={`skel-${i}`} className="border-t border-ifx-gray-100">
                  {selectable && <td className="px-3 py-3" />}
                  {visibleColumns.map((col) => (
                    <td key={col.id} className="px-3 py-3">
                      <div className="h-4 w-24 rounded shimmer" />
                    </td>
                  ))}
                </tr>
              ))
            ) : pageRows.length === 0 ? (
              <tr>
                <td
                  colSpan={visibleColumns.length + (selectable ? 1 : 0)}
                  className="px-3 py-16 text-center text-sm text-ifx-gray-400"
                >
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              pageRows.map((row, i) => {
                const rowId = getRowId(row, currentPage * pageSize + i);
                const isSelected = selected.has(rowId);
                return (
                  <tr
                    key={rowId}
                    onClick={() => onRowClick?.(row)}
                    className={cn(
                      "border-t border-ifx-gray-100 transition-colors",
                      onRowClick && "cursor-pointer hover:bg-ifx-lavender/50",
                      isSelected && "bg-ifx-blue/5",
                    )}
                  >
                    {selectable && (
                      <td className="w-10 px-3 py-2" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleRowSelection(rowId)}
                          className="h-4 w-4 rounded border-ifx-gray-200 text-ifx-blue focus:ring-ifx-blue/40"
                          aria-label="Select row"
                        />
                      </td>
                    )}
                    {visibleColumns.map((col) => {
                      const value = col.accessor(row);
                      return (
                        <td
                          key={col.id}
                          className={cn(
                            "px-3 py-2 text-ifx-gray-900 whitespace-nowrap",
                            alignClass(col.align),
                            col.pinned && "sticky left-0 bg-white",
                            isSelected && col.pinned && "bg-ifx-blue/5",
                          )}
                        >
                          {defaultCell(col, value, row)}
                        </td>
                      );
                    })}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination footer */}
      {!loading && totalRows > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-ifx-gray-400">
          <div>
            Displaying {currentPage * pageSize + 1}–
            {Math.min((currentPage + 1) * pageSize, totalRows)} of{" "}
            <span className="font-semibold text-ifx-gray-700">
              {totalRows.toLocaleString()}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-1.5">
              Rows per page
              <select
                value={pageSize}
                onChange={(e) => {
                  setPageSize(Number(e.target.value));
                  setPage(0);
                }}
                className="rounded border border-ifx-gray-100 bg-white px-2 py-1 text-xs text-ifx-gray-700"
              >
                {pageSizeOptions.map((size) => (
                  <option key={size} value={size}>
                    {size}
                  </option>
                ))}
              </select>
            </label>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={currentPage === 0}
                className="rounded border border-ifx-gray-100 bg-white px-2 py-1 text-ifx-gray-700 disabled:opacity-40"
              >
                Prev
              </button>
              <span className="px-2">
                Page {currentPage + 1} / {pageCount}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
                disabled={currentPage >= pageCount - 1}
                className="rounded border border-ifx-gray-100 bg-white px-2 py-1 text-ifx-gray-700 disabled:opacity-40"
              >
                Next
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Hydration sentinel keeps React from complaining about SSR mismatch */}
      {!hydrated && <span className="sr-only">Loading table preferences…</span>}
    </div>
  );
}

function exportToCsv(
  name: string,
  headers: string[],
  rows: string[][],
  ext: "csv" | "xls",
) {
  if (typeof window === "undefined") return;
  const escape = (v: string) => {
    if (v.includes(",") || v.includes("\"") || v.includes("\n")) {
      return `"${v.replace(/"/g, '""')}"`;
    }
    return v;
  };
  const lines = [headers.map(escape).join(","), ...rows.map((r) => r.map(escape).join(","))];
  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${name}-${new Date().toISOString().slice(0, 10)}.${ext}`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
