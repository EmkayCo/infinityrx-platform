"use client";

import React, { use, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Shield,
  AlertTriangle,
  CheckCircle,
  Settings,
  FlaskConical,
  Save,
} from "lucide-react";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { Skeleton } from "@shared/components/skeleton";
import { apiGet, apiPatch, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { TradingPartner, TransactionType, PartnerStatus } from "@shared/types/edi";
import { cn, formatDate } from "@shared/lib/format";

const STATUS_BADGE: Record<PartnerStatus, string> = {
  active: "bg-green-900/40 text-green-300",
  test: "bg-yellow-900/40 text-yellow-300",
  disabled: "bg-slate-700 text-slate-400",
};

const ALL_TRANSACTION_TYPES: TransactionType[] = ["835", "837", "270", "271", "276", "277", "278", "834", "999"];

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
      <h3 className="text-sm font-semibold text-slate-200 mb-4">{title}</h3>
      {children}
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between py-2 border-b border-ifx-border-dark/50 last:border-0">
      <span className="text-sm text-slate-400 flex-shrink-0 w-40">{label}</span>
      <div className="text-right">{value}</div>
    </div>
  );
}

export default function TradingPartnerDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const queryClient = useQueryClient();
  const [editMode, setEditMode] = useState(false);
  const [draftName, setDraftName] = useState("");
  const [draftStatus, setDraftStatus] = useState<PartnerStatus>("active");
  const [draftTypes, setDraftTypes] = useState<TransactionType[]>([]);

  const { data: partner, isLoading } = useQuery<TradingPartner>({
    queryKey: ["trading-partner", id],
    queryFn: () =>
      apiGet<TradingPartner>(buildUrl(`${API_URLS.edi}/api/v1/trading-partners/${id}`)),
    staleTime: 30_000,
  });

  const toggleTestMode = useMutation({
    mutationFn: () =>
      apiPatch<TradingPartner>(buildUrl(`${API_URLS.edi}/api/v1/trading-partners/${id}`), {
        test_mode: !partner?.test_mode,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["trading-partner", id] });
      void queryClient.invalidateQueries({ queryKey: ["trading-partners"] });
    },
  });

  const saveEdits = useMutation({
    mutationFn: () =>
      apiPatch<TradingPartner>(buildUrl(`${API_URLS.edi}/api/v1/trading-partners/${id}`), {
        name: draftName,
        status: draftStatus,
        accepted_transaction_types: draftTypes,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["trading-partner", id] });
      void queryClient.invalidateQueries({ queryKey: ["trading-partners"] });
      setEditMode(false);
    },
  });

  function enterEdit() {
    if (!partner) return;
    setDraftName(partner.name);
    setDraftStatus(partner.status);
    setDraftTypes([...partner.accepted_transaction_types]);
    setEditMode(true);
  }

  function toggleType(t: TransactionType) {
    setDraftTypes((prev) =>
      prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]
    );
  }

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Skeleton className="h-64" />
          <Skeleton className="h-64" />
        </div>
      </div>
    );
  }

  if (!partner) {
    return (
      <div className="p-6 text-center py-16">
        <p className="text-slate-400">Trading partner not found.</p>
        <button onClick={() => router.back()} className="mt-4 text-teal-400 hover:text-teal-300 text-sm">
          Go back
        </button>
      </div>
    );
  }

  const certDays = partner.days_until_cert_expiry ?? 999;
  const certWarning = certDays < 90;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start gap-3">
        <button onClick={() => router.back()} className="mt-1 text-slate-400 hover:text-slate-200 transition-colors">
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-3 flex-wrap">
            <Shield className="w-5 h-5 text-teal-400" />
            <h1 className="text-2xl font-bold text-white">{partner.name}</h1>
            <span className={cn("text-xs px-2 py-0.5 rounded capitalize", STATUS_BADGE[partner.status])}>
              {partner.status}
            </span>
            {partner.test_mode && (
              <span className="text-xs px-2 py-0.5 rounded bg-yellow-900/40 text-yellow-300 flex items-center gap-1">
                <FlaskConical className="w-3 h-3" />
                Test Mode
              </span>
            )}
          </div>
          <p className="text-slate-400 text-sm mt-1">
            Partner ID: <span className="font-mono">{partner.partner_id}</span>
            &nbsp;·&nbsp; Updated: {formatDate(partner.updated_at)}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => void toggleTestMode.mutate()}
            disabled={toggleTestMode.isPending}
            className={cn(
              "flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
              partner.test_mode
                ? "bg-green-700/20 border border-green-700/40 text-green-300 hover:bg-green-700/30"
                : "bg-yellow-900/20 border border-yellow-700/40 text-yellow-300 hover:bg-yellow-900/30"
            )}
          >
            <FlaskConical className="w-4 h-4" />
            {partner.test_mode ? "Go Production" : "Enable Test Mode"}
          </button>
          {editMode ? (
            <button
              onClick={() => void saveEdits.mutate()}
              disabled={saveEdits.isPending}
              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-teal-600 hover:bg-teal-500 text-white text-sm font-medium transition-colors"
            >
              <Save className="w-4 h-4" />
              {saveEdits.isPending ? "Saving…" : "Save"}
            </button>
          ) : (
            <button
              onClick={enterEdit}
              className="flex items-center gap-2 px-3 py-2 rounded-lg border border-ifx-border-dark bg-ifx-surface-dark text-slate-300 hover:text-white text-sm transition-colors"
            >
              <Settings className="w-4 h-4" />
              Edit Config
            </button>
          )}
        </div>
      </div>

      {/* Cert warning banner */}
      {certWarning && (
        <div className={cn(
          "rounded-lg border p-3 flex items-center gap-3",
          certDays < 30
            ? "bg-red-900/20 border-red-800/40 text-red-300"
            : "bg-orange-900/20 border-orange-700/40 text-orange-300"
        )}>
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          <p className="text-sm">
            Certificate <strong>{partner.cert_name}</strong> expires in{" "}
            <strong>{certDays} days</strong> ({partner.cert_expiry ? formatDate(partner.cert_expiry) : "unknown"}).{" "}
            <button
              onClick={() => router.push("/edi/certs")}
              className="underline hover:opacity-80"
            >
              Manage certificates →
            </button>
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Partner Config */}
        <ErrorBoundary>
          <SectionCard title="Partner Configuration">
            {editMode ? (
              <div className="space-y-4">
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Partner Name</label>
                  <input
                    value={draftName}
                    onChange={(e) => setDraftName(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-navy-900 border border-ifx-border-dark text-white text-sm focus:outline-none focus:ring-1 focus:ring-teal-500"
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Status</label>
                  <select
                    value={draftStatus}
                    onChange={(e) => setDraftStatus(e.target.value as PartnerStatus)}
                    className="w-full px-3 py-2 rounded-lg bg-navy-900 border border-ifx-border-dark text-white text-sm focus:outline-none focus:ring-1 focus:ring-teal-500"
                  >
                    <option value="active">Active</option>
                    <option value="test">Test</option>
                    <option value="disabled">Disabled</option>
                  </select>
                </div>
              </div>
            ) : (
              <>
                <InfoRow label="Partner ID" value={<span className="font-mono text-xs text-slate-300">{partner.partner_id}</span>} />
                <InfoRow label="Status" value={
                  <span className={cn("text-xs px-2 py-0.5 rounded capitalize", STATUS_BADGE[partner.status])}>
                    {partner.status}
                  </span>
                } />
                <InfoRow label="Protocols" value={
                  <div className="flex gap-1 flex-wrap justify-end">
                    {partner.protocols.map((p) => (
                      <span key={p} className="text-xs px-1.5 py-0.5 rounded bg-navy-700 text-slate-300">{p}</span>
                    ))}
                  </div>
                } />
                <InfoRow label="Mode" value={
                  <span className={cn("text-xs px-2 py-0.5 rounded", partner.test_mode ? "bg-yellow-900/40 text-yellow-300" : "bg-green-900/40 text-green-300")}>
                    {partner.test_mode ? "Test" : "Production"}
                  </span>
                } />
                <InfoRow label="Created" value={<span className="text-sm text-slate-300">{formatDate(partner.created_at)}</span>} />
                <InfoRow label="Updated" value={<span className="text-sm text-slate-300">{formatDate(partner.updated_at)}</span>} />
              </>
            )}
          </SectionCard>
        </ErrorBoundary>

        {/* Connection Details */}
        <ErrorBoundary>
          <SectionCard title="Connection Details">
            {partner.as2_id && (
              <InfoRow label="AS2 ID" value={<span className="font-mono text-xs text-slate-300">{partner.as2_id}</span>} />
            )}
            {partner.sftp_host && (
              <>
                <InfoRow label="SFTP Host" value={<span className="font-mono text-xs text-slate-300">{partner.sftp_host}</span>} />
                {partner.sftp_port && (
                  <InfoRow label="SFTP Port" value={<span className="font-mono text-xs text-slate-300">{partner.sftp_port}</span>} />
                )}
                {partner.sftp_username && (
                  <InfoRow label="SFTP User" value={<span className="font-mono text-xs text-slate-300">{partner.sftp_username}</span>} />
                )}
              </>
            )}
            {partner.cert_name && (
              <InfoRow label="Certificate" value={
                <div className="text-right">
                  <p className="text-sm text-slate-300">{partner.cert_name}</p>
                  {partner.cert_expiry && (
                    <p className={cn(
                      "text-xs",
                      certDays < 30 ? "text-red-400" : certDays < 90 ? "text-yellow-400" : "text-slate-500"
                    )}>
                      Expires {formatDate(partner.cert_expiry)}
                      {certWarning && ` (${certDays}d)`}
                    </p>
                  )}
                </div>
              } />
            )}
            {!partner.as2_id && !partner.sftp_host && !partner.cert_name && (
              <p className="text-sm text-slate-500">No connection details configured.</p>
            )}
          </SectionCard>
        </ErrorBoundary>
      </div>

      {/* Transaction Types */}
      <ErrorBoundary>
        <SectionCard title="Accepted Transaction Types">
          {editMode ? (
            <div className="flex flex-wrap gap-2">
              {ALL_TRANSACTION_TYPES.map((t) => (
                <button
                  key={t}
                  onClick={() => toggleType(t)}
                  className={cn(
                    "px-3 py-1.5 rounded-lg text-sm font-mono font-medium border transition-colors",
                    draftTypes.includes(t)
                      ? "bg-teal-600/30 border-teal-600/60 text-teal-300"
                      : "bg-navy-900 border-ifx-border-dark text-slate-400 hover:text-slate-200"
                  )}
                >
                  {t}
                </button>
              ))}
              <p className="text-xs text-slate-500 mt-2 w-full">
                {draftTypes.length} transaction type{draftTypes.length !== 1 ? "s" : ""} selected
              </p>
            </div>
          ) : (
            <div className="flex flex-wrap gap-2">
              {ALL_TRANSACTION_TYPES.map((t) => {
                const active = partner.accepted_transaction_types.includes(t);
                return (
                  <div
                    key={t}
                    className={cn(
                      "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-mono font-medium border",
                      active
                        ? "bg-teal-600/20 border-teal-600/40 text-teal-300"
                        : "bg-navy-900/40 border-slate-700/40 text-slate-500"
                    )}
                  >
                    {active ? (
                      <CheckCircle className="w-3 h-3" />
                    ) : (
                      <span className="w-3 h-3 rounded-full border border-slate-600 inline-block" />
                    )}
                    {t}
                  </div>
                );
              })}
            </div>
          )}
        </SectionCard>
      </ErrorBoundary>
    </div>
  );
}
