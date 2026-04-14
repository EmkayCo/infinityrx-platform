// Invoice detail page.
"use client";

import React from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter, useParams } from "next/navigation";
import { ArrowLeft, Download, Send, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";
import { getInvoice, approveInvoice, sendInvoice, voidInvoice, getInvoicePdf } from "@shared/lib/billing-api";
import { DollarDisplay } from "@shared/components/dollar-display";
import { SkeletonCard } from "@shared/components/skeleton";
import { formatDate, formatDateTime } from "@shared/lib/format";

export default function InvoiceDetailPage() {
  const router = useRouter();
  const params = useParams();
  const id = params?.id as string;
  const queryClient = useQueryClient();

  const { data: invoice, isLoading } = useQuery({
    queryKey: ["invoice", id],
    queryFn: () => getInvoice(id),
    enabled: !!id,
  });

  const approveMutation = useMutation({
    mutationFn: () => approveInvoice(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["invoice", id] });
      toast.success("Invoice approved");
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to approve"),
  });

  const sendMutation = useMutation({
    mutationFn: () => sendInvoice(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["invoice", id] });
      toast.success("Invoice sent");
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to send"),
  });

  const voidMutation = useMutation({
    mutationFn: () => voidInvoice(id, "Voided by operator"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["invoice", id] });
      toast.success("Invoice voided");
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to void"),
  });

  const handleDownloadPdf = async () => {
    const blob = await getInvoicePdf(id);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `invoice-${invoice?.invoice_number ?? id}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (isLoading) {
    return (
      <div className="p-6 space-y-4 max-w-3xl mx-auto">
        <SkeletonCard />
        <SkeletonCard />
      </div>
    );
  }

  if (!invoice) {
    return (
      <div className="p-6 max-w-3xl mx-auto">
        <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-6 text-center">
          <p className="text-red-400">Invoice not found or service unavailable.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-5">
      {/* Header */}
      <div className="flex items-start gap-3">
        <button
          onClick={() => router.push("/billing/invoices")}
          className="p-1.5 rounded hover:bg-navy-700 text-slate-400 mt-0.5"
          aria-label="Back to invoices"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold text-slate-100">
              Invoice {invoice.invoice_number}
            </h1>
            <span
              className={`px-2 py-0.5 rounded text-xs font-medium ${
                invoice.status === "paid"
                  ? "bg-green-500/20 text-green-300"
                  : invoice.status === "overdue"
                  ? "bg-red-500/20 text-red-400"
                  : "bg-blue-500/20 text-blue-300"
              }`}
            >
              {invoice.status}
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-0.5">{invoice.client_name}</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleDownloadPdf}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded border border-ifx-border-dark text-slate-300 hover:bg-navy-700"
          >
            <Download className="w-4 h-4" />
            PDF
          </button>
          {invoice.status === "generated" && (
            <>
              <button
                onClick={() => approveMutation.mutate()}
                disabled={approveMutation.isPending}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded bg-teal-500 text-white hover:bg-teal-600 disabled:opacity-40"
              >
                <CheckCircle2 className="w-4 h-4" />
                Approve
              </button>
            </>
          )}
          {(invoice.status as string) === "approved" && (
            <button
              onClick={() => sendMutation.mutate()}
              disabled={sendMutation.isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded bg-teal-500 text-white hover:bg-teal-600 disabled:opacity-40"
            >
              <Send className="w-4 h-4" />
              Send to client
            </button>
          )}
        </div>
      </div>

      {/* Summary */}
      <div className="rounded-lg border border-ifx-border-dark bg-navy-700/20 p-5">
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <p className="text-slate-500 mb-1">Total Amount</p>
            <DollarDisplay amount={invoice.total_amount} size="xl" showVerbal />
          </div>
          <div className="space-y-1.5">
            <div className="flex justify-between">
              <span className="text-slate-500">Due Date</span>
              <span className="text-slate-200">{formatDate(invoice.due_date)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Issued</span>
              <span className="text-slate-200">{formatDate(invoice.issued_at)}</span>
            </div>
            {invoice.paid_at && (
              <div className="flex justify-between">
                <span className="text-slate-500">Paid</span>
                <span className="text-green-400">{formatDate(invoice.paid_at)}</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Line items */}
      {invoice.line_items.length > 0 && (
        <div className="rounded-lg border border-ifx-border-dark overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-navy-900/80 border-b border-ifx-border-dark">
              <tr>
                <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-400 uppercase tracking-wide">Description</th>
                <th className="px-4 py-2.5 text-right text-xs font-semibold text-slate-400 uppercase tracking-wide">Qty</th>
                <th className="px-4 py-2.5 text-right text-xs font-semibold text-slate-400 uppercase tracking-wide">Unit Price</th>
                <th className="px-4 py-2.5 text-right text-xs font-semibold text-slate-400 uppercase tracking-wide">Total</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ifx-border-dark/50">
              {invoice.line_items.map((item) => (
                <tr key={item.id} className="hover:bg-navy-700/20">
                  <td className="px-4 py-2.5 text-slate-200">{item.description}</td>
                  <td className="px-4 py-2.5 text-right text-slate-400 tabular-nums">
                    {item.quantity.toLocaleString()}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <DollarDisplay amount={item.unit_price} size="sm" />
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <DollarDisplay amount={item.total} size="sm" showScale />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Timeline */}
      {invoice.timeline.length > 0 && (
        <div className="rounded-lg border border-ifx-border-dark bg-navy-700/20 p-4">
          <h3 className="text-sm font-semibold text-slate-300 mb-3">Activity</h3>
          <div className="space-y-3">
            {invoice.timeline.map((entry, i) => (
              <div key={i} className="flex gap-3 text-sm">
                <span className="text-slate-500 whitespace-nowrap">
                  {formatDateTime(entry.timestamp)}
                </span>
                <span className="text-slate-300">
                  <span className="font-medium">{entry.actor}</span> {entry.action}
                  {entry.notes && (
                    <span className="text-slate-500"> — {entry.notes}</span>
                  )}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Void option */}
      {["generated", "sent"].includes(invoice.status) && (
        <div className="pt-2 border-t border-ifx-border-dark">
          <button
            onClick={() => {
              if (confirm("Void this invoice? This cannot be undone.")) {
                voidMutation.mutate();
              }
            }}
            disabled={voidMutation.isPending}
            className="text-sm text-red-400 hover:underline disabled:opacity-40"
          >
            Void invoice
          </button>
        </div>
      )}
    </div>
  );
}
