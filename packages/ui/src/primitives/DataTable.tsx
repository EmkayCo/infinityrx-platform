export interface Column<T> {
  key: keyof T;
  header: string;
}

export interface DataTableProps<T extends object> {
  columns: Column<T>[];
  rows: T[];
  emptyMessage?: string;
  className?: string;
}

/**
 * Reference table primitive. Simple HTML table — no virtualization, no sorting.
 * TanStack Table integration is a future task when a vertical needs it.
 * Every column header maps to a row cell via column.key.
 */
export function DataTable<T extends object>({
  columns,
  rows,
  emptyMessage = "No data",
  className,
}: DataTableProps<T>) {
  return (
    <table className={["irx-data-table", className].filter(Boolean).join(" ")}>
      <thead>
        <tr>
          {columns.map((col) => (
            <th key={String(col.key)}>{col.header}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.length === 0 ? (
          <tr>
            <td colSpan={columns.length}>{emptyMessage}</td>
          </tr>
        ) : (
          rows.map((row, i) => (
            <tr key={i}>
              {columns.map((col) => (
                <td key={String(col.key)}>{String(row[col.key] ?? "")}</td>
              ))}
            </tr>
          ))
        )}
      </tbody>
    </table>
  );
}
