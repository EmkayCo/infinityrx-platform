"use client";

import Link from "next/link";
import { Settings, ArrowLeft, ToggleLeft, ToggleRight, Globe, Lock, Bell, Database, FlaskConical } from "lucide-react";

const FEATURE_FLAGS = [
  { key: "enable_340b_split_billing", label: "340B Split Billing", on: true, scope: "global" },
  { key: "enable_copay_accumulator", label: "Copay Accumulator Programs", on: true, scope: "tenant" },
  { key: "enable_fhir_pa_api", label: "FHIR Prior Auth API (CMS-0057-F)", on: false, scope: "global" },
  { key: "enable_real_time_benefit_check", label: "Real-Time Benefit Check (RTBC)", on: false, scope: "tenant" },
  { key: "enable_ai_denial_prediction", label: "AI Denial Prediction", on: true, scope: "tenant" },
  { key: "enable_glp1_dashboards", label: "GLP-1 Trend Dashboards", on: true, scope: "global" },
];

const SYSTEM_SETTINGS = [
  { key: "session_idle_timeout_minutes", label: "Session Idle Timeout", value: "15 minutes" },
  { key: "max_concurrent_sessions", label: "Max Concurrent Sessions per User", value: "5" },
  { key: "approval_threshold_billing", label: "Billing Cycle Approval Threshold", value: "$1,000,000" },
  { key: "approval_threshold_payment", label: "Payment Batch Approval Threshold", value: "$500,000" },
  { key: "approval_threshold_nacha", label: "NACHA Transmission Approval Threshold", value: "$500,000" },
  { key: "audit_retention_days", label: "Audit Log Retention", value: "2,555 days (7 years)" },
  { key: "phi_access_log_required", label: "PHI Access Logging", value: "Required (HIPAA 2026)" },
];

export default function AdminConfigPage() {
  return (
    <div className="max-w-7xl mx-auto p-6">
      <div className="mb-6 flex items-center gap-2 text-sm text-muted-foreground">
        <Link href="/admin/users" className="hover:text-foreground inline-flex items-center gap-1">
          <ArrowLeft className="h-3.5 w-3.5" /> Admin
        </Link>
        <span>/</span>
        <span className="text-foreground">Configuration</span>
      </div>

      <div className="mb-6 flex items-center gap-3">
        <div className="rounded-md bg-teal-500/10 p-2">
          <Settings className="h-5 w-5 text-teal-500" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">Configuration</h1>
          <p className="text-sm text-muted-foreground">Platform-wide feature flags and system settings.</p>
        </div>
      </div>

      <Link
        href="/admin/config/change-sets"
        className="mb-6 flex items-center justify-between gap-4 rounded-lg border bg-card p-4 transition hover:bg-muted/30"
      >
        <div className="flex items-center gap-3">
          <div className="rounded-md bg-amber-500/10 p-2">
            <FlaskConical className="h-4 w-4 text-amber-500" />
          </div>
          <div>
            <h2 className="text-sm font-semibold">Change-set workflow</h2>
            <p className="text-xs text-muted-foreground">
              Simulate staged configuration changes against recent claims,
              then apply when ready.
            </p>
          </div>
        </div>
        <span className="text-xs text-muted-foreground">Open →</span>
      </Link>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-lg border bg-card">
          <header className="flex items-center justify-between border-b px-4 py-3">
            <div className="flex items-center gap-2">
              <ToggleRight className="h-4 w-4 text-teal-500" />
              <h2 className="text-sm font-semibold">Feature Flags</h2>
            </div>
            <span className="text-xs text-muted-foreground">{FEATURE_FLAGS.length} flags</span>
          </header>
          <ul className="divide-y">
            {FEATURE_FLAGS.map((flag) => (
              <li key={flag.key} className="flex items-center justify-between gap-4 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">{flag.label}</p>
                  <p className="mt-0.5 font-mono text-[11px] text-muted-foreground">{flag.key}</p>
                </div>
                <span className="text-[11px] uppercase tracking-wider text-muted-foreground">{flag.scope}</span>
                {flag.on ? (
                  <ToggleRight className="h-6 w-6 text-teal-500" />
                ) : (
                  <ToggleLeft className="h-6 w-6 text-slate-400" />
                )}
              </li>
            ))}
          </ul>
        </section>

        <section className="rounded-lg border bg-card">
          <header className="flex items-center justify-between border-b px-4 py-3">
            <div className="flex items-center gap-2">
              <Lock className="h-4 w-4 text-teal-500" />
              <h2 className="text-sm font-semibold">System Settings</h2>
            </div>
            <span className="text-xs text-muted-foreground">{SYSTEM_SETTINGS.length} settings</span>
          </header>
          <ul className="divide-y">
            {SYSTEM_SETTINGS.map((s) => (
              <li key={s.key} className="px-4 py-3">
                <div className="flex items-baseline justify-between gap-4">
                  <p className="text-sm font-medium">{s.label}</p>
                  <p className="text-sm font-medium tabular-nums">{s.value}</p>
                </div>
                <p className="mt-0.5 font-mono text-[11px] text-muted-foreground">{s.key}</p>
              </li>
            ))}
          </ul>
        </section>

        <section className="rounded-lg border bg-card">
          <header className="flex items-center gap-2 border-b px-4 py-3">
            <Globe className="h-4 w-4 text-teal-500" />
            <h2 className="text-sm font-semibold">Environment</h2>
          </header>
          <dl className="divide-y text-sm">
            <div className="flex justify-between px-4 py-2.5">
              <dt className="text-muted-foreground">Environment</dt>
              <dd className="font-mono">development</dd>
            </div>
            <div className="flex justify-between px-4 py-2.5">
              <dt className="text-muted-foreground">Region</dt>
              <dd>East US (Azure)</dd>
            </div>
            <div className="flex justify-between px-4 py-2.5">
              <dt className="text-muted-foreground">Build</dt>
              <dd className="font-mono">v0.1.0+demo</dd>
            </div>
          </dl>
        </section>

        <section className="rounded-lg border bg-card">
          <header className="flex items-center gap-2 border-b px-4 py-3">
            <Bell className="h-4 w-4 text-teal-500" />
            <h2 className="text-sm font-semibold">Notifications</h2>
          </header>
          <ul className="divide-y text-sm">
            <li className="flex items-center justify-between px-4 py-2.5">
              <span>Email transport</span>
              <span className="text-muted-foreground">SendGrid (configured)</span>
            </li>
            <li className="flex items-center justify-between px-4 py-2.5">
              <span>SMS transport</span>
              <span className="text-muted-foreground">Twilio (configured)</span>
            </li>
            <li className="flex items-center justify-between px-4 py-2.5">
              <span>In-app push</span>
              <span className="text-muted-foreground">SSE — enabled</span>
            </li>
          </ul>
        </section>

        <section className="rounded-lg border bg-card lg:col-span-2">
          <header className="flex items-center gap-2 border-b px-4 py-3">
            <Database className="h-4 w-4 text-teal-500" />
            <h2 className="text-sm font-semibold">Storage & Encryption</h2>
          </header>
          <div className="grid gap-3 px-4 py-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
            <div className="rounded-md border bg-muted/30 p-3">
              <p className="text-[11px] uppercase tracking-wider text-muted-foreground">Database</p>
              <p className="mt-0.5 font-medium">PostgreSQL 17</p>
              <p className="text-xs text-muted-foreground">RLS + tenant_id fence enabled</p>
            </div>
            <div className="rounded-md border bg-muted/30 p-3">
              <p className="text-[11px] uppercase tracking-wider text-muted-foreground">Cache</p>
              <p className="mt-0.5 font-medium">Redis 7.4</p>
              <p className="text-xs text-muted-foreground">Tenant-prefixed keys</p>
            </div>
            <div className="rounded-md border bg-muted/30 p-3">
              <p className="text-[11px] uppercase tracking-wider text-muted-foreground">PHI Encryption</p>
              <p className="mt-0.5 font-medium">AES-256-GCM</p>
              <p className="text-xs text-muted-foreground">Tenant-scoped AAD</p>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
