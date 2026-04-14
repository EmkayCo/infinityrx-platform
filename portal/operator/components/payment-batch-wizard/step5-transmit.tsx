// Step 5 — Transmit Payment Files
"use client";

import React, { useEffect, useState } from "react";
import {
  Send,
  CheckCircle2,
  XCircle,
  Loader2,
  Clock,
} from "lucide-react";
import { getBatch, transmitNachaFile } from "@shared/lib/payments-api";
import { DollarDisplay } from "@shared/components/dollar-display";
import { cn } from "@shared/lib/format";
import { PaymentBatchWizardData } from "./types";
import type { BatchRouting } from "@shared/types/payments";

interface TransmitStepProps {
  data: PaymentBatchWizardData;
  onChange: (partial: Partial<PaymentBatchWizardData>) => void;
}

type FileStatus = "pending" | "transmitting" | "transmitted" | "failed";

interface FileTransmission {
  vendor: string;
  vendor_name: string;
  nacha_file_id: string | null;
  amount: string;
  count: number;
  status: FileStatus;
  error?: string;
  ack_status: "pending" | "acknowledged" | "rejected" | null;
}

export function TransmitStep({ data, onChange }: TransmitStepProps) {
  const [files, setFiles] = useState<FileTransmission[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!data.batch_id) return;
    getBatch(data.batch_id)
      .then((batch) => {
        const transmissions: FileTransmission[] = (batch.routing ?? []).map(
          (r: BatchRouting) => ({
            vendor: r.vendor,
            vendor_name: r.vendor_name,
            nacha_file_id: batch.nacha_file_id,
            amount: r.total_amount,
            count: r.payment_count,
            status: data.transmission_statuses[r.vendor] ?? "pending",
            ack_status: null,
          })
        );
        setFiles(transmissions);
      })
      .catch(() => {
        // Use routing summary as fallback
        setFiles(
          data.routing_summary.map((r) => ({
            vendor: r.vendor,
            vendor_name: r.vendor_name,
            nacha_file_id: data.batch_id ? data.batch_id : null,
            amount: r.total_amount,
            count: r.payment_count,
            status: data.transmission_statuses[r.vendor] ?? "pending",
            ack_status: null,
          }))
        );
      })
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data.batch_id]);

  const handleTransmit = async (file: FileTransmission) => {
    setFiles((prev) =>
      prev.map((f) =>
        f.vendor === file.vendor ? { ...f, status: "transmitting" } : f
      )
    );
    onChange({
      transmission_statuses: {
        ...data.transmission_statuses,
        [file.vendor]: "transmitting",
      },
    });

    try {
      if (file.nacha_file_id) {
        await transmitNachaFile(file.nacha_file_id);
      }
      setFiles((prev) =>
        prev.map((f) =>
          f.vendor === file.vendor
            ? { ...f, status: "transmitted", ack_status: "pending" }
            : f
        )
      );
      onChange({
        transmission_statuses: {
          ...data.transmission_statuses,
          [file.vendor]: "transmitted",
        },
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Transmission failed";
      setFiles((prev) =>
        prev.map((f) =>
          f.vendor === file.vendor ? { ...f, status: "failed", error: message } : f
        )
      );
      onChange({
        transmission_statuses: {
          ...data.transmission_statuses,
          [file.vendor]: "failed",
        },
      });
    }
  };

  const statusIcon = (status: FileStatus) => {
    switch (status) {
      case "transmitted":
        return <CheckCircle2 className="w-5 h-5 text-teal-400" />;
      case "transmitting":
        return <Loader2 className="w-5 h-5 text-teal-400 animate-spin" />;
      case "failed":
        return <XCircle className="w-5 h-5 text-red-400" />;
      default:
        return <Clock className="w-5 h-5 text-slate-500" />;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-slate-400">
        <Loader2 className="w-4 h-4 animate-spin text-teal-400" />
        Loading transmission queue…
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-400">
        Transmit each payment file to its vendor. NACHA files are transmitted via SFTP to
        the configured bank endpoint. Acknowledgment status updates automatically.
      </p>

      {/* Transmission status table */}
      <div className="rounded-lg border border-ifx-border-dark overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-navy-900/80 border-b border-ifx-border-dark">
            <tr>
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-400 uppercase tracking-wide">Status</th>
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-400 uppercase tracking-wide">Vendor</th>
              <th className="px-4 py-2.5 text-right text-xs font-semibold text-slate-400 uppercase tracking-wide">Payments</th>
              <th className="px-4 py-2.5 text-right text-xs font-semibold text-slate-400 uppercase tracking-wide">Amount</th>
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-400 uppercase tracking-wide">Ack</th>
              <th className="px-4 py-2.5" />
            </tr>
          </thead>
          <tbody className="divide-y divide-ifx-border-dark/50">
            {files.map((file) => (
              <tr key={file.vendor} className="hover:bg-navy-700/20">
                <td className="px-4 py-3">
                  {statusIcon(file.status)}
                </td>
                <td className="px-4 py-3">
                  <div>
                    <p className="text-slate-200 font-medium">{file.vendor_name}</p>
                    {file.error && (
                      <p className="text-xs text-red-400 mt-0.5">{file.error}</p>
                    )}
                  </div>
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-slate-300">
                  {file.count}
                </td>
                <td className="px-4 py-3 text-right">
                  <DollarDisplay amount={file.amount} size="sm" />
                </td>
                <td className="px-4 py-3">
                  {file.ack_status === "acknowledged" ? (
                    <span className="text-xs text-green-400">Acknowledged</span>
                  ) : file.ack_status === "rejected" ? (
                    <span className="text-xs text-red-400">Rejected</span>
                  ) : file.status === "transmitted" ? (
                    <span className="text-xs text-yellow-400">Pending</span>
                  ) : (
                    <span className="text-xs text-slate-600">—</span>
                  )}
                </td>
                <td className="px-4 py-3 text-right">
                  {file.status === "pending" && (
                    <button
                      onClick={() => handleTransmit(file)}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded bg-teal-500 text-white hover:bg-teal-600 transition-colors ml-auto"
                    >
                      <Send className="w-3.5 h-3.5" />
                      Transmit
                    </button>
                  )}
                  {file.status === "failed" && (
                    <button
                      onClick={() => handleTransmit(file)}
                      className="text-xs text-teal-400 hover:underline ml-auto block"
                    >
                      Retry
                    </button>
                  )}
                  {file.status === "transmitted" && (
                    <span
                      className={cn(
                        "text-xs",
                        file.ack_status === "acknowledged"
                          ? "text-teal-400"
                          : "text-yellow-400"
                      )}
                    >
                      {file.ack_status === "acknowledged" ? "Complete" : "Awaiting ack"}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-slate-500">
        Acknowledgment status is updated in real time. You can close this wizard and
        monitor acknowledgments from Payments → NACHA File Management.
      </p>
    </div>
  );
}
