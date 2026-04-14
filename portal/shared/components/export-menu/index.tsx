"use client";

import React from "react";
import { Download, FileText, Table, Clipboard, Share2 } from "lucide-react";
import { cn } from "@shared/lib/format";
import type { ExportFormat } from "@shared/hooks/use-export";

interface ExportMenuProps {
  onExport?: (format: ExportFormat) => void | Promise<void>;
  onExportCsv?: () => void;
  onExportExcel?: () => void;
  onExportPdf?: () => void;
  onExportClipboard?: () => void;
  onShare?: () => void;
  label?: string;
  disabled?: boolean;
  className?: string;
}

const EXPORT_OPTIONS = [
  { format: "csv" as ExportFormat, label: "Export CSV", Icon: Table },
  { format: "excel" as ExportFormat, label: "Export Excel", Icon: FileText },
  { format: "pdf" as ExportFormat, label: "Export PDF", Icon: FileText },
  { format: "clipboard" as ExportFormat, label: "Copy to Clipboard", Icon: Clipboard },
];

export function ExportMenu({
  onExport,
  onExportCsv,
  onExportExcel,
  onExportPdf,
  onExportClipboard,
  onShare,
  label = "Export",
  disabled,
  className,
}: ExportMenuProps) {
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  async function handleFormat(format: ExportFormat) {
    setOpen(false);
    if (onExport) {
      await onExport(format);
      return;
    }
    switch (format) {
      case "csv": onExportCsv?.(); break;
      case "excel": onExportExcel?.(); break;
      case "pdf": onExportPdf?.(); break;
      case "clipboard": onExportClipboard?.(); break;
    }
  }

  return (
    <div className={cn("relative", className)} ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        disabled={disabled}
        className="flex items-center gap-2 px-3 py-1.5 text-sm rounded-md border bg-card hover:bg-accent transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        aria-haspopup="true"
        aria-expanded={open}
        aria-label="Export options"
      >
        <Download className="w-4 h-4" />
        {label}
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 w-48 rounded-lg border bg-popover shadow-lg z-50 overflow-hidden">
          {EXPORT_OPTIONS.map(({ format, label: optLabel, Icon }) => (
            <button
              key={format}
              onClick={() => handleFormat(format)}
              className="flex w-full items-center gap-2.5 px-4 py-2 text-sm hover:bg-accent transition-colors text-left"
            >
              <Icon className="h-4 w-4 text-muted-foreground" />
              {optLabel}
            </button>
          ))}
          {onShare && (
            <>
              <div className="border-t" />
              <button
                onClick={() => { onShare(); setOpen(false); }}
                className="flex w-full items-center gap-2.5 px-4 py-2 text-sm hover:bg-accent transition-colors text-left"
              >
                <Share2 className="h-4 w-4 text-muted-foreground" />
                Share link (24h)
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
