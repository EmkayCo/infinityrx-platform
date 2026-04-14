"use client";

import React, { useState } from "react";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  flexRender,
  type ColumnDef,
  type CellContext,
  type SortingState,
  type ColumnFiltersState,
  type VisibilityState,
  type RowSelectionState,
} from "@tanstack/react-table";
import { cn } from "@shared/lib/format";
import { Skeleton } from "@shared/components/skeleton";
import { EmptyState } from "@shared/components/empty-state";

export type { ColumnDef, CellContext };

/**
 * Column definition alias that resolves TypeScript contextual inference issues
 * with `cell: (c) => ...` callbacks in strict mode. Uses `any` as the value
 * generic so that `cell` and `header` callbacks are typed explicitly enough
 * for TypeScript to infer callback parameter types without explicit annotations.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type ColDef<TData> = ColumnDef<TData, any>;

interface DataTableProps<TData> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  columns: ColumnDef<TData, any>[] | ColDef<TData>[];
  data: TData[];
  isLoading?: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
  onRowClick?: (row: TData) => void;
  getRowId?: (row: TData) => string;
  enableRowSelection?: boolean;
  bulkActions?: React.ReactNode;
  className?: string;
  stickyHeader?: boolean;
}

export function DataTable<TData>({
  columns,
  data,
  isLoading,
  emptyTitle = "No results",
  emptyDescription,
  onRowClick,
  getRowId,
  enableRowSelection,
  bulkActions,
  className,
  stickyHeader,
}: DataTableProps<TData>) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({});
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  const [globalFilter, setGlobalFilter] = useState("");

  const table = useReactTable({
    data,
    columns,
    state: {
      sorting,
      columnFilters,
      columnVisibility,
      rowSelection,
      globalFilter,
    },
    enableRowSelection,
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onColumnVisibilityChange: setColumnVisibility,
    onRowSelectionChange: setRowSelection,
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getRowId,
  });

  if (isLoading) {
    return (
      <div className={cn("rounded-lg border border-ifx-border-dark overflow-hidden", className)}>
        <div className="p-4">
          <Skeleton className="h-8 w-64 mb-4" />
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex gap-4">
                {columns.map((_, j) => (
                  <Skeleton key={j} className="h-4 flex-1" />
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  const selectedCount = Object.keys(rowSelection).length;

  return (
    <div className={cn("space-y-2", className)}>
      <div className="flex items-center gap-3">
        <input
          type="search"
          placeholder="Search..."
          value={globalFilter}
          onChange={(e) => setGlobalFilter(e.target.value)}
          className="flex-1 max-w-xs px-3 py-1.5 text-sm rounded-md border border-ifx-border-dark bg-ifx-surface-dark text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-teal-500/40"
        />
        {enableRowSelection && selectedCount > 0 && bulkActions && (
          <div className="flex items-center gap-3 px-4 py-2 rounded-lg bg-teal-900/30 border border-teal-600/30">
            <span className="text-sm text-teal-300 font-medium">
              {selectedCount} selected
            </span>
            {bulkActions}
          </div>
        )}
      </div>

      <div className="rounded-lg border border-ifx-border-dark overflow-auto">
        <table className="w-full text-sm">
          <thead className={cn(
            "bg-navy-900/80 border-b border-ifx-border-dark",
            stickyHeader && "sticky top-0 z-10"
          )}>
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((header) => (
                  <th
                    key={header.id}
                    className="px-4 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wide select-none"
                    onClick={header.column.getToggleSortingHandler()}
                    style={{ cursor: header.column.getCanSort() ? "pointer" : undefined }}
                  >
                    <span className="flex items-center gap-1">
                      {header.isPlaceholder
                        ? null
                        : flexRender(header.column.columnDef.header, header.getContext())}
                      {header.column.getIsSorted() === "asc" && " ↑"}
                      {header.column.getIsSorted() === "desc" && " ↓"}
                    </span>
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="text-center py-12 text-slate-500">
                  <EmptyState title={emptyTitle} description={emptyDescription} />
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row) => (
                <tr
                  key={row.id}
                  onClick={onRowClick ? () => onRowClick(row.original) : undefined}
                  className={cn(
                    "border-b border-ifx-border-dark/50 hover:bg-navy-700/30 transition-colors",
                    onRowClick && "cursor-pointer",
                    row.getIsSelected() && "bg-teal-900/10"
                  )}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="px-4 py-3 text-slate-200">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
