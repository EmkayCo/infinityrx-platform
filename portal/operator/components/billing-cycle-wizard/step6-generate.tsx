// Step 6 — Generate & Transmit
"use client";

import React, { useEffect, useState } from "react";
import {
  CheckCircle2,
  Download,
  Send,
  Loader2,
  AlertTriangle,
} from "lucide-react";
import { getCycle, transmitNacha } from "@shared/lib/billing-api";
import { BillingCycleWizardData } from "./types";
import type { CycleArtifact } from "@shared/types/billing";

interface GenerateStepProps {
  data: BillingCycleWizardData;
  onChange: (partial: Partial<BillingCycleWizardData>) => void;
}

type ArtifactStatus = "pending" | "ready" | "error";

const ARTIFACT_LABELS: Record<CycleArtifact["type"], string> = {
  saasant_excel: "SaaSant Excel",
  "835": "835 Remittance Files",
  nacha: "NACHA ACH File",
  report: "Reports",
};

export function GenerateStep({ data }: GenerateStepProps) {
  const [artifacts, setArtifacts] = useState<CycleArtifact[]>([]);
  const [loading, setLoading] = useState(true);
  const [transmitting, setTransmitting] = useState<string | null>(null);
  const [transmitError, setTransmitError] = useState<string | null>(null);
  const [transmitConfirm, setTransmitConfirm] = useState<string | null>(null);

  useEffect(() => {
    if (!data.generated_cycle_id) {
      setLoading(false);
      return;
    }
    const poll = async () => {
      try {
        const cycle = await getCycle(data.generated_cycle_id!);
        setArtifacts(cycle.artifacts ?? []);
        // If all artifacts are generated, stop polling
        const allDone = cycle.artifacts.every((a) => a.generated_at);
        if (!allDone) {
          setTimeout(poll, 2000);
        } else {
          setLoading(false);
        }
      } catch {
        setLoading(false);
      }
    };
    poll();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data.generated_cycle_id]);

  const handleDownload = (artifact: CycleArtifact) => {
    const a = document.createElement("a");
    a.href = artifact.download_url;
    a.download = artifact.filename;
    a.click();
  };

  const handleTransmit = async (artifact: CycleArtifact) => {
    if (!data.generated_cycle_id) return;
    setTransmitting(artifact.id);
    setTransmitError(null);
    try {
      await transmitNacha({
        cycle_id: data.generated_cycle_id,
        artifact_id: artifact.id,
      });
      // Refresh artifacts
      const cycle = await getCycle(data.generated_cycle_id);
      setArtifacts(cycle.artifacts ?? []);
    } catch (err) {
      setTransmitError(err instanceof Error ? err.message : "Transmission failed");
    } finally {
      setTransmitting(null);
      setTransmitConfirm(null);
    }
  };

  // Show expected artifact types if none loaded yet
  const artifactTypes: CycleArtifact["type"][] = ["saasant_excel", "835", "nacha", "report"];

  return (
    <div className="space-y-5">
      <div className="space-y-3">
        {artifactTypes.map((type) => {
          const artifact = artifacts.find((a) => a.type === type);
          const status: ArtifactStatus = artifact?.generated_at
            ? "ready"
            : loading
            ? "pending"
            : "pending";

          return (
            <ArtifactRow
              key={type}
              type={type}
              label={ARTIFACT_LABELS[type]}
              artifact={artifact ?? null}
              status={status}
              loading={loading && !artifact}
              isTransmitting={transmitting === artifact?.id}
              transmitConfirm={transmitConfirm}
              onTransmitRequest={(id) => setTransmitConfirm(id)}
              onTransmitConfirm={() => artifact && handleTransmit(artifact)}
              onTransmitCancel={() => setTransmitConfirm(null)}
              onDownload={() => artifact && handleDownload(artifact)}
            />
          );
        })}
      </div>

      {transmitError && (
        <div className="flex items-center gap-2 rounded border border-red-500/30 bg-red-500/5 p-3">
          <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
          <span className="text-sm text-red-400">{transmitError}</span>
        </div>
      )}

      <p className="text-xs text-slate-500">
        All generated files are available for download above. NACHA files must be
        transmitted to your bank to initiate ACH payments.
      </p>
    </div>
  );
}

function ArtifactRow({
  type,
  label,
  artifact,
  status,
  loading,
  isTransmitting,
  transmitConfirm,
  onTransmitRequest,
  onTransmitConfirm,
  onTransmitCancel,
  onDownload,
}: {
  type: CycleArtifact["type"];
  label: string;
  artifact: CycleArtifact | null;
  status: ArtifactStatus;
  loading: boolean;
  isTransmitting: boolean;
  transmitConfirm: string | null;
  onTransmitRequest: (id: string) => void;
  onTransmitConfirm: () => void;
  onTransmitCancel: () => void;
  onDownload: () => void;
}) {
  const isReady = status === "ready";
  const isNacha = type === "nacha";

  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-ifx-border-dark bg-navy-700/20 px-4 py-3">
      <div className="flex items-center gap-3">
        {loading ? (
          <Loader2 className="w-5 h-5 text-slate-500 animate-spin" />
        ) : isReady ? (
          <CheckCircle2 className="w-5 h-5 text-teal-400" />
        ) : (
          <div className="w-5 h-5 rounded-full border-2 border-slate-600 animate-pulse" />
        )}
        <div>
          <p className="text-sm font-medium text-slate-200">{label}</p>
          {artifact?.filename && (
            <p className="text-xs text-slate-500 font-mono">{artifact.filename}</p>
          )}
          {isNacha && artifact?.transmitted_at && (
            <p className="text-xs text-teal-400 mt-0.5">
              Transmitted ·{" "}
              {artifact.ack_status === "acknowledged" ? (
                <span className="text-green-400">Acknowledged</span>
              ) : (
                <span className="text-yellow-400">Pending ack</span>
              )}
            </p>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2">
        {isReady && (
          <button
            onClick={onDownload}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded border border-ifx-border-dark text-slate-300 hover:bg-navy-700 transition-colors"
          >
            <Download className="w-3.5 h-3.5" />
            Download
          </button>
        )}
        {isNacha && isReady && !artifact?.transmitted_at && (
          <>
            {transmitConfirm === artifact?.id ? (
              <div className="flex items-center gap-2">
                <span className="text-xs text-yellow-400">Confirm transmit?</span>
                <button
                  onClick={onTransmitConfirm}
                  disabled={isTransmitting}
                  className="px-3 py-1.5 text-xs rounded bg-teal-500 text-white hover:bg-teal-600 disabled:opacity-40"
                >
                  {isTransmitting ? "Transmitting…" : "Yes, transmit"}
                </button>
                <button
                  onClick={onTransmitCancel}
                  className="px-2 py-1.5 text-xs text-slate-400 hover:text-slate-200"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <button
                onClick={() => artifact && onTransmitRequest(artifact.id)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded bg-teal-500 text-white hover:bg-teal-600 transition-colors"
              >
                <Send className="w-3.5 h-3.5" />
                Transmit to bank
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
}
