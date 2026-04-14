"use client";

import { useCallback } from "react";

export interface ExportColumn {
  header: string;
  accessor: string;
  format?: (value: unknown) => string;
}

export type ExportFormat = "csv" | "excel" | "pdf" | "clipboard";

export interface UseExportOptions {
  filename: string;
  title?: string;
  columns: ExportColumn[];
}

export interface UseExportReturn {
  exportData: (rows: Record<string, unknown>[], format: ExportFormat) => Promise<void>;
  isExporting: boolean;
}

function getRowValue(row: Record<string, unknown>, col: ExportColumn): string {
  const value = row[col.accessor];
  if (col.format) return col.format(value);
  if (value === null || value === undefined) return "";
  return String(value);
}

export function useExport(options: UseExportOptions): UseExportReturn {
  const { filename, title, columns } = options;

  const exportCSV = useCallback(
    (rows: Record<string, unknown>[]) => {
      const headers = columns.map((c) => `"${c.header}"`).join(",");
      const dataRows = rows.map((row) =>
        columns.map((col) => `"${getRowValue(row, col).replace(/"/g, '""')}"`).join(",")
      );
      const csv = [headers, ...dataRows].join("\n");
      const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${filename}.csv`;
      link.click();
      URL.revokeObjectURL(url);
    },
    [columns, filename]
  );

  const exportExcel = useCallback(
    async (rows: Record<string, unknown>[]) => {
      const ExcelJS = (await import("exceljs")).default;
      const workbook = new ExcelJS.Workbook();
      const sheet = workbook.addWorksheet(title ?? "Data");

      // Header row
      sheet.addRow(columns.map((c) => c.header));
      const headerRow = sheet.getRow(1);
      headerRow.font = { bold: true };
      headerRow.fill = {
        type: "pattern",
        pattern: "solid",
        fgColor: { argb: "FF0B1D3A" }, // navy-900
      };
      headerRow.font = { bold: true, color: { argb: "FFFFFFFF" } };

      // Data rows
      rows.forEach((row) => {
        sheet.addRow(columns.map((col) => getRowValue(row, col)));
      });

      // Auto-fit columns
      sheet.columns.forEach((col) => {
        let maxLen = 10;
        col.eachCell?.({ includeEmpty: false }, (cell) => {
          const len = cell.value ? String(cell.value).length : 0;
          if (len > maxLen) maxLen = len;
        });
        col.width = Math.min(maxLen + 2, 60);
      });

      const buffer = await workbook.xlsx.writeBuffer();
      const blob = new Blob([buffer], {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${filename}.xlsx`;
      link.click();
      URL.revokeObjectURL(url);
    },
    [columns, filename, title]
  );

  const exportPDF = useCallback(
    async (rows: Record<string, unknown>[]) => {
      const { jsPDF } = await import("jspdf");
      const autoTable = (await import("jspdf-autotable")).default;

      const doc = new jsPDF({ orientation: "landscape" });
      if (title) {
        doc.setFontSize(16);
        doc.text(title, 14, 20);
        doc.setFontSize(10);
        doc.text(
          `Generated: ${new Date().toLocaleString()} — CONFIDENTIAL`,
          14,
          28
        );
      }

      autoTable(doc, {
        head: [columns.map((c) => c.header)],
        body: rows.map((row) => columns.map((col) => getRowValue(row, col))),
        startY: title ? 34 : 14,
        styles: { fontSize: 8 },
        headStyles: { fillColor: [11, 29, 58] }, // navy-900
      });

      doc.save(`${filename}.pdf`);
    },
    [columns, filename, title]
  );

  const exportClipboard = useCallback(
    async (rows: Record<string, unknown>[]) => {
      const headers = columns.map((c) => c.header).join("\t");
      const dataRows = rows.map((row) =>
        columns.map((col) => getRowValue(row, col)).join("\t")
      );
      const text = [headers, ...dataRows].join("\n");
      await navigator.clipboard.writeText(text);
    },
    [columns]
  );

  const exportData = useCallback(
    async (rows: Record<string, unknown>[], format: ExportFormat) => {
      switch (format) {
        case "csv":
          exportCSV(rows);
          break;
        case "excel":
          await exportExcel(rows);
          break;
        case "pdf":
          await exportPDF(rows);
          break;
        case "clipboard":
          await exportClipboard(rows);
          break;
      }
    },
    [exportCSV, exportExcel, exportPDF, exportClipboard]
  );

  return { exportData, isExporting: false };
}
