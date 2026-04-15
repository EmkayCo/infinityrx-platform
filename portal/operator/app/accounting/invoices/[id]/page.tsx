"use client";

import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Download, CheckCircle, Send } from "lucide-react";
import { apiGet, apiPost } from "@shared/lib/api-client";
import { DetailPageLayout } from "@/components/ui/detail-page-layout";
import { InfoCard } from "@/components/ui/info-card";
import { StatusBadge } from "@/components/ui/status-badge";
import { cn } from "@shared/lib/format";

interface InvoiceLineItem {
  id: string;
  description: string;
  quantity: number;
  unit_price: string;
  total: string;
}

interface InvoiceTimelineEntry {
  action: string;
  actor: string;
  timestamp: string;
  notes?: string | null;
}

interface Invoice {
  id: string;
  invoice_number: string;
  client_id?: string;
  client_name?: string;
  cycle_id?: string;
  status: string;
  total_amount: string;
  due_date?: string;
  issued_at?: string;
  paid_at?: string | null;
  pdf_url?: string | null;
  line_items?: InvoiceLineItem[];
  timeline?: InvoiceTimelineEntry[];
}

export default function InvoiceDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const queryClient = useQueryClient();

  const { data: invoice, isLoading } = useQuery<Invoice>({
    queryKey: ["invoice", id],
    queryFn: () => apiGet<Invoice>(`/billing/v1/invoices/${id}`),
    enabled: !!id,
  });

  const sendMutation = useMutation({
    mutationFn: () => apiPost(`/billing/v1/invoices/${id}/send`, {}),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["invoice", id] }),
  });

  const markPaidMutation = useMutation({
    mutationFn: () => apiPost(`/api/v1/accounting/invoices/${id}/mark-paid`, {}),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["invoice", id] }),
  });

  if (isLoading) {
    return (
      <DetailPageLayout
        backLink={{ href: "/accounting/invoices", label: "Back to Invoices" }}
        title="Loading invoice…"
      >
        <div className="h-40 rounded-lg bg-white shimmer" />
      </DetailPageLayout>
    );
  }

  if (!invoice) {
    return (
      <DetailPageLayout
        backLink={{ href: "/accounting/invoices", label: "Back to Invoices" }}
        title="Invoice not found"
      >
        <div className="rounded-md bg-ifx-error-light border border-ifx-error/20 p-4 text-sm text-ifx-error-text">
          Invoice not found.
        </div>
      </DetailPageLayout>
    );
  }

  const lineItems = invoice.line_items ?? [];
  const lineItemsTotal = lineItems.reduce((s, li) => s + Number(li.total), 0).toFixed(2);

  return (
    <DetailPageLayout
      backLink={{ href: "/accounting/invoices", label: "Back to Invoices" }}
      eyebrow="Invoice"
      title={invoice.invoice_number}
      subtitle={
        <div className="flex items-center gap-3">
          {invoice.client_name && <span className="text-ifx-gray-700">{invoice.client_name}</span>}
          <StatusBadge status={invoice.status} />
        </div>
      }
      actions={
        <>
          {invoice.pdf_url && (
            <a
              href={invoice.pdf_url}
              className="inline-flex items-center gap-1.5 rounded-md border border-ifx-gray-100 bg-white px-3 py-1.5 text-xs font-medium text-ifx-gray-700 hover:bg-ifx-gray-50 transition-colors"
            >
              <Download className="h-3.5 w-3.5" />
              Download PDF
            </a>
          )}
          {invoice.status === "generated" && (
            <button
              type="button"
              onClick={() => sendMutation.mutate()}
              className="inline-flex items-center gap-1.5 rounded-md bg-ifx-blue px-3 py-1.5 text-xs font-medium text-white hover:bg-ifx-blue/90 transition-colors"
            >
              <Send className="h-3.5 w-3.5" />
              Send to Client
            </button>
          )}
          {["sent", "overdue"].includes(invoice.status) && (
            <button
              type="button"
              onClick={() => markPaidMutation.mutate()}
              className="inline-flex items-center gap-1.5 rounded-md bg-ifx-success px-3 py-1.5 text-xs font-medium text-white hover:bg-ifx-success/90 transition-colors"
            >
              <CheckCircle className="h-3.5 w-3.5" />
              Mark as Paid
            </button>
          )}
        </>
      }
      summaryCards={[
        {
          label: "Invoice Total",
          value: invoice.total_amount,
          format: "currency",
          accentColor: "var(--ifx-navy)",
        },
        {
          label: "Status",
          value: invoice.status.toUpperCase(),
          format: "raw",
          accentColor:
            invoice.status === "paid"
              ? "var(--ifx-success)"
              : invoice.status === "overdue"
                ? "var(--ifx-error)"
                : "var(--ifx-warning)",
        },
        {
          label: "Due Date",
          value: invoice.due_date
            ? new Date(invoice.due_date).toLocaleDateString("en-US")
            : "—",
          format: "raw",
          accentColor: "var(--ifx-blue)",
        },
        {
          label: "Paid Date",
          value: invoice.paid_at
            ? new Date(invoice.paid_at).toLocaleDateString("en-US")
            : "—",
          format: "raw",
          accentColor: "var(--ifx-success)",
        },
      ]}
    >
      {/* Info cards */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <InfoCard
          title="Invoice Information"
          fields={[
            { label: "Invoice Number", value: invoice.invoice_number, mono: true },
            { label: "Client", value: invoice.client_name },
            { label: "Issued", value: invoice.issued_at, format: "date" },
            { label: "Due Date", value: invoice.due_date, format: "date" },
            { label: "Paid Date", value: invoice.paid_at, format: "date" },
            { label: "Status", value: <StatusBadge status={invoice.status} /> },
          ]}
        />
        <InfoCard
          title="Financial Summary"
          fields={[
            { label: "Invoice Total", value: invoice.total_amount, format: "currency" },
            { label: "Line Items Total", value: lineItemsTotal, format: "currency" },
            { label: "PDF Available", value: invoice.pdf_url ? "Yes" : "No" },
          ]}
        />
      </div>

      {/* Line items */}
      {lineItems.length > 0 && (
        <div className="rounded-lg bg-white ifx-card-shadow overflow-hidden">
          <header className="border-b border-ifx-gray-100 px-4 py-3">
            <h3 className="text-sm font-bold text-ifx-gray-900">Line Items</h3>
          </header>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-ifx-gray-100 bg-ifx-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-ifx-gray-400">Description</th>
                  <th className="px-4 py-2 text-right text-xs font-semibold uppercase tracking-wider text-ifx-gray-400">Quantity</th>
                  <th className="px-4 py-2 text-right text-xs font-semibold uppercase tracking-wider text-ifx-gray-400">Unit Price</th>
                  <th className="px-4 py-2 text-right text-xs font-semibold uppercase tracking-wider text-ifx-gray-400">Total</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ifx-gray-100">
                {lineItems.map((li) => (
                  <tr key={li.id} className="hover:bg-ifx-gray-50">
                    <td className="px-4 py-3 text-ifx-gray-700">{li.description}</td>
                    <td className="px-4 py-3 text-right text-ifx-gray-700">
                      {li.quantity.toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-ifx-gray-700">
                      ${Number(li.unit_price).toLocaleString("en-US", { minimumFractionDigits: 2 })}
                    </td>
                    <td className="px-4 py-3 text-right font-mono font-semibold text-ifx-gray-900">
                      ${Number(li.total).toLocaleString("en-US", { minimumFractionDigits: 2 })}
                    </td>
                  </tr>
                ))}
                <tr className="border-t-2 border-ifx-gray-100 bg-ifx-gray-50">
                  <td colSpan={3} className="px-4 py-3 text-right text-sm font-bold text-ifx-gray-900">
                    Total
                  </td>
                  <td className="px-4 py-3 text-right font-mono font-bold text-ifx-navy">
                    ${Number(invoice.total_amount).toLocaleString("en-US", { minimumFractionDigits: 2 })}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Timeline */}
      {(invoice.timeline ?? []).length > 0 && (
        <div className="rounded-lg bg-white ifx-card-shadow overflow-hidden">
          <header className="border-b border-ifx-gray-100 px-4 py-3">
            <h3 className="text-sm font-bold text-ifx-gray-900">Activity Timeline</h3>
          </header>
          <ol className="divide-y divide-ifx-gray-100">
            {(invoice.timeline ?? []).map((entry, i) => (
              <li key={i} className="flex items-start gap-3 px-4 py-3 text-sm">
                <div
                  className={cn(
                    "mt-0.5 h-2 w-2 rounded-full shrink-0",
                    entry.action === "paid" ? "bg-ifx-success" :
                    entry.action === "sent" ? "bg-ifx-blue" : "bg-ifx-gray-300",
                  )}
                />
                <div className="min-w-0 flex-1">
                  <span className="font-medium capitalize text-ifx-gray-900">{entry.action}</span>
                  {entry.notes && (
                    <span className="ml-1 text-ifx-gray-400">— {entry.notes}</span>
                  )}
                  <div className="mt-0.5 text-xs text-ifx-gray-400">
                    {entry.actor} · {new Date(entry.timestamp).toLocaleDateString("en-US")}
                  </div>
                </div>
              </li>
            ))}
          </ol>
        </div>
      )}
    </DetailPageLayout>
  );
}
