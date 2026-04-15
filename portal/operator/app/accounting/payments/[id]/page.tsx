"use client";

import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle, XCircle, Send } from "lucide-react";
import { apiGet, apiPost } from "@shared/lib/api-client";
import { DetailPageLayout } from "@/components/ui/detail-page-layout";
import { InfoCard } from "@/components/ui/info-card";
import { StatusBadge } from "@/components/ui/status-badge";
import { ConfigurableDataTable, type Column } from "@/components/ui/configurable-data-table";
import { cn } from "@shared/lib/format";

interface IndividualPayment {
  id: string;
  pharmacy_npi?: string;
  pharmacy_name?: string;
  claim_count?: number;
  amount: string;
  payment_type?: string;
  routing_number?: string;
  account_number?: string;
  status?: string;
  check_number?: string;
}

interface PaymentBatch {
  id: string;
  vendor?: string;
  vendor_name?: string;
  nrid?: string;
  status: string;
  total_amount: string;
  payment_count?: number;
  claim_count?: number;
  created_at: string;
  approved_at?: string | null;
  approved_by?: string | null;
  settled_at?: string | null;
  nacha_file_id?: string;
  payments?: IndividualPayment[];
}

const PAYMENT_COLUMNS: Column<IndividualPayment>[] = [
  {
    id: "pharmacy_name",
    header: "Pharmacy",
    accessor: (r) => r.pharmacy_name,
    defaultVisible: true,
  },
  {
    id: "pharmacy_npi",
    header: "NPI",
    accessor: (r) => r.pharmacy_npi,
    format: "npi",
    defaultVisible: true,
  },
  {
    id: "claim_count",
    header: "Claims",
    accessor: (r) => r.claim_count,
    format: "number",
    align: "right",
    defaultVisible: true,
  },
  {
    id: "amount",
    header: "Amount",
    accessor: (r) => r.amount,
    format: "currency",
    align: "right",
    defaultVisible: true,
  },
  {
    id: "payment_type",
    header: "Type",
    accessor: (r) => r.payment_type ?? "ACH",
    defaultVisible: true,
  },
  {
    id: "status",
    header: "Status",
    accessor: (r) => r.status ?? "pending",
    format: "status",
    defaultVisible: true,
  },
  {
    id: "routing_number",
    header: "Routing",
    accessor: (r) => r.routing_number,
    defaultVisible: false,
  },
  {
    id: "account_number",
    header: "Account",
    accessor: (r) => r.account_number,
    defaultVisible: false,
  },
  {
    id: "check_number",
    header: "Check #",
    accessor: (r) => r.check_number,
    defaultVisible: false,
  },
];

export default function PaymentBatchDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const queryClient = useQueryClient();

  const { data: batch, isLoading } = useQuery<PaymentBatch>({
    queryKey: ["payment-batch", id],
    queryFn: () => apiGet<PaymentBatch>(`/batches/${id}`),
    enabled: !!id,
  });

  const { data: paymentsData } = useQuery<{ items: IndividualPayment[] }>({
    queryKey: ["batch-payments", id],
    queryFn: () => apiGet<{ items: IndividualPayment[] }>(`/api/v1/accounting/payments/${id}/payments`),
    enabled: !!id,
  });

  const approveMutation = useMutation({
    mutationFn: () => apiPost(`/batches/${id}/approve`, {}),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["payment-batch", id] }),
  });

  const submitMutation = useMutation({
    mutationFn: () => apiPost(`/batches/${id}/submit`, {}),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["payment-batch", id] }),
  });

  const voidMutation = useMutation({
    mutationFn: () => apiPost(`/batches/${id}/void`, {}),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["payment-batch", id] }),
  });

  if (isLoading) {
    return (
      <DetailPageLayout
        backLink={{ href: "/accounting/payments", label: "Back to Payments" }}
        title="Loading batch…"
      >
        <div className="h-40 rounded-lg bg-white shimmer" />
      </DetailPageLayout>
    );
  }

  if (!batch) {
    return (
      <DetailPageLayout
        backLink={{ href: "/accounting/payments", label: "Back to Payments" }}
        title="Batch not found"
      >
        <div className="rounded-md bg-ifx-error-light border border-ifx-error/20 p-4 text-sm text-ifx-error-text">
          Payment batch not found.
        </div>
      </DetailPageLayout>
    );
  }

  const payments = paymentsData?.items ?? [];

  return (
    <DetailPageLayout
      backLink={{ href: "/accounting/payments", label: "Back to Payments" }}
      eyebrow="Payment Batch"
      title={`Batch ${batch.id.slice(0, 8)}`}
      subtitle={
        <div className="flex items-center gap-3">
          {batch.vendor_name && <span className="text-ifx-gray-700">{batch.vendor_name}</span>}
          <StatusBadge status={batch.status} />
        </div>
      }
      actions={
        <>
          {batch.status === "pending_approval" && (
            <button
              type="button"
              onClick={() => approveMutation.mutate()}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-md bg-ifx-success px-3 py-1.5 text-xs font-medium text-white hover:bg-ifx-success/90 transition-colors",
              )}
            >
              <CheckCircle className="h-3.5 w-3.5" />
              Approve
            </button>
          )}
          {batch.status === "approved" && (
            <button
              type="button"
              onClick={() => submitMutation.mutate()}
              className="inline-flex items-center gap-1.5 rounded-md bg-ifx-navy px-3 py-1.5 text-xs font-medium text-white hover:bg-ifx-navy-dark transition-colors"
            >
              <Send className="h-3.5 w-3.5" />
              Submit / Transmit
            </button>
          )}
          {!["settled", "voided"].includes(batch.status) && (
            <button
              type="button"
              onClick={() => voidMutation.mutate()}
              className="inline-flex items-center gap-1.5 rounded-md border border-ifx-gray-100 bg-white px-3 py-1.5 text-xs font-medium text-ifx-error hover:bg-ifx-error-light transition-colors"
            >
              <XCircle className="h-3.5 w-3.5" />
              Void Batch
            </button>
          )}
        </>
      }
      summaryCards={[
        {
          label: "Total Amount",
          value: batch.total_amount,
          format: "currency",
          accentColor: "var(--ifx-navy)",
        },
        {
          label: "Payments",
          value: batch.payment_count ?? batch.claim_count ?? 0,
          format: "number",
          accentColor: "var(--ifx-blue)",
        },
        {
          label: "Status",
          value: batch.status.replace("_", " ").toUpperCase(),
          format: "raw",
          accentColor: "var(--ifx-warning)",
        },
        {
          label: "Vendor",
          value: batch.vendor_name ?? batch.vendor ?? "—",
          format: "raw",
          accentColor: "var(--ifx-blue)",
        },
      ]}
    >
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <InfoCard
          title="Batch Details"
          fields={[
            { label: "Batch ID", value: batch.id, mono: true },
            { label: "NRID", value: batch.nrid, mono: true },
            { label: "Vendor", value: batch.vendor_name ?? batch.vendor },
            { label: "Status", value: <StatusBadge status={batch.status} /> },
            { label: "Created", value: batch.created_at, format: "date" },
            { label: "Settled", value: batch.settled_at, format: "date" },
          ]}
        />
        <InfoCard
          title="Approval"
          fields={[
            { label: "Approved By", value: batch.approved_by },
            { label: "Approved At", value: batch.approved_at, format: "date" },
            { label: "NACHA File", value: batch.nacha_file_id ?? "Not generated" },
          ]}
        />
      </div>

      {/* Individual payments */}
      <div className="rounded-lg bg-white ifx-card-shadow overflow-hidden">
        <header className="border-b border-ifx-gray-100 px-4 py-3">
          <h3 className="text-sm font-bold text-ifx-gray-900">
            Individual Payments
            {payments.length > 0 && (
              <span className="ml-2 text-sm font-normal text-ifx-gray-400">
                ({payments.length})
              </span>
            )}
          </h3>
        </header>
        <ConfigurableDataTable
          tableId="batch-payments"
          columns={PAYMENT_COLUMNS}
          data={payments}
          getRowId={(r) => r.id}
          emptyMessage="Individual payment records not yet available for this batch."
          pagination={{ pageSize: 25 }}
          exportable
        />
      </div>
    </DetailPageLayout>
  );
}
