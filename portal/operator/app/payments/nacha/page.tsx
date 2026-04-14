"use client";

import Link from "next/link";
import { ArrowLeft, FileText, Download, Send } from "lucide-react";

export default function NachaFilesPage() {
  return (
    <div className="max-w-7xl mx-auto p-6">
      <div className="mb-6 flex items-center gap-2 text-sm text-muted-foreground">
        <Link href="/payments" className="hover:text-foreground inline-flex items-center gap-1">
          <ArrowLeft className="h-3.5 w-3.5" /> Payments
        </Link>
        <span>/</span>
        <span className="text-foreground">NACHA Files</span>
      </div>

      <div className="mb-6">
        <h1 className="text-2xl font-bold">NACHA File Management</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Generated NACHA ACH files awaiting transmission, transmitted, and acknowledged.
        </p>
      </div>

      <div className="rounded-lg border bg-card">
        <div className="border-b px-4 py-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold">Files</h2>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-muted/40 text-xs uppercase tracking-wider text-muted-foreground">
            <tr>
              <th className="px-4 py-2 text-left">Filename</th>
              <th className="px-4 py-2 text-left">Bank</th>
              <th className="px-4 py-2 text-right">Entries</th>
              <th className="px-4 py-2 text-right">Total</th>
              <th className="px-4 py-2 text-left">Status</th>
              <th className="px-4 py-2 text-left">Transmitted</th>
              <th className="px-4 py-2 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {[
              { name: "NACHA_20260414_001.txt", bank: "Webster Bank", entries: 89, total: "$891,234.56", status: "transmitted", txt: "2026-04-14 10:32" },
              { name: "NACHA_20260413_007.txt", bank: "Webster Bank", entries: 124, total: "$1,402,890.10", status: "acknowledged", txt: "2026-04-13 16:18" },
              { name: "NACHA_20260413_006.txt", bank: "Chase ACH", entries: 47, total: "$320,455.20", status: "acknowledged", txt: "2026-04-13 14:02" },
              { name: "NACHA_20260412_005.txt", bank: "Webster Bank", entries: 203, total: "$2,108,400.75", status: "settled", txt: "2026-04-12 11:30" },
            ].map((f) => (
              <tr key={f.name} className="border-t hover:bg-muted/20">
                <td className="px-4 py-2.5 font-mono text-xs flex items-center gap-2">
                  <FileText className="h-3.5 w-3.5 text-muted-foreground" />
                  {f.name}
                </td>
                <td className="px-4 py-2.5">{f.bank}</td>
                <td className="px-4 py-2.5 text-right tabular-nums">{f.entries}</td>
                <td className="px-4 py-2.5 text-right tabular-nums font-medium">{f.total}</td>
                <td className="px-4 py-2.5">
                  <span
                    className={
                      f.status === "settled"
                        ? "rounded-full bg-green-500/10 px-2 py-0.5 text-[11px] text-green-600 dark:text-green-400"
                        : f.status === "acknowledged"
                          ? "rounded-full bg-teal-500/10 px-2 py-0.5 text-[11px] text-teal-600 dark:text-teal-400"
                          : "rounded-full bg-amber-500/10 px-2 py-0.5 text-[11px] text-amber-600 dark:text-amber-400"
                    }
                  >
                    {f.status}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-xs text-muted-foreground">{f.txt}</td>
                <td className="px-4 py-2.5 text-right">
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs hover:bg-muted"
                  >
                    <Download className="h-3 w-3" />
                    Download
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="mt-4 text-xs text-muted-foreground">
        <Send className="inline h-3 w-3 mr-1" />
        Transmission flow lives inside the Payment Batch wizard at <Link href="/payments/batches/new" className="text-teal-600 hover:underline">/payments/batches/new</Link>.
      </p>
    </div>
  );
}
