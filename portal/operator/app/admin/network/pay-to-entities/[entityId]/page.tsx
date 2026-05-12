"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import * as Tabs from "@radix-ui/react-tabs";
import {
  ArrowLeft, Building2, CheckCircle2, Loader2, Plus, ShieldCheck,
} from "lucide-react";

import { ApiClientError } from "@shared/lib/api-client";
import {
  getPayToEntity, getBankingForEntity, listBankingChangeLog,
  createBanking, verifyBanking, terminateBanking,
  type PayToEntity, type BankingRecord, type BankingChangeLogEntry,
} from "@shared/lib/paysync-api";

import { AuditLogTimeline } from "@/components/paysync/audit-log-timeline";
import { DestructiveActionDialog } from "@/components/paysync/destructive-action-dialog";

interface PageParams { entityId: string; }

export default function PayToEntityDetailPage(
  { params }: { params: Promise<PageParams> },
) {
  const { entityId } = use(params);
  const [entity, setEntity] = useState<PayToEntity | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getPayToEntity(entityId)
      .then(setEntity)
      .catch((e: unknown) => {
        const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
        toast.error(`Failed to load entity — ${msg}`);
      })
      .finally(() => setLoading(false));
  }, [entityId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12 text-muted-foreground">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Loading entity…
      </div>
    );
  }
  if (!entity) {
    return (
      <div className="p-6">
        <p className="text-rose-500">Entity not found.</p>
        <Link href="/admin/network/pay-to-entities" className="text-sky-500 hover:underline">
          ← Back
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[1400px] p-6">
      <div className="mb-4 flex items-center gap-2 text-sm text-muted-foreground">
        <Link href="/admin/network/pay-to-entities"
              className="inline-flex items-center gap-1 hover:text-foreground">
          <ArrowLeft className="h-3.5 w-3.5" /> Pay-to entities
        </Link>
        <span>/</span>
        <span className="font-mono text-foreground">{entity.external_id}</span>
      </div>

      <header className="mb-6 flex items-start gap-3">
        <div className="rounded-md bg-violet-500/10 p-2">
          <Building2 className="h-5 w-5 text-violet-500" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">{entity.name}</h1>
          <p className="text-sm text-muted-foreground">
            {entity.entity_type} · status {entity.status} · effective from{" "}
            {entity.effective_from}
            {entity.termination_date && ` until ${entity.termination_date}`}
          </p>
        </div>
      </header>

      <Tabs.Root defaultValue="banking">
        <Tabs.List className="flex flex-wrap gap-1 border-b">
          {[
            ["banking", "Banking"], ["change-log", "Change log"],
          ].map(([v, l]) => (
            <Tabs.Trigger key={v} value={v}
                          className="px-3 py-2 text-sm text-muted-foreground hover:text-foreground data-[state=active]:border-b-2 data-[state=active]:border-violet-500 data-[state=active]:text-foreground">
              {l}
            </Tabs.Trigger>
          ))}
        </Tabs.List>

        <Tabs.Content value="banking" className="pt-6">
          <BankingTab entityId={entityId} />
        </Tabs.Content>
        <Tabs.Content value="change-log" className="pt-6">
          <ChangeLogTab entityId={entityId} />
        </Tabs.Content>
      </Tabs.Root>
    </div>
  );
}

function BankingTab({ entityId }: { entityId: string }) {
  const [rows, setRows] = useState<BankingRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [terminateOpen, setTerminateOpen] = useState<string | null>(null);
  const [terminateReason, setTerminateReason] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  function refresh() {
    setLoading(true);
    getBankingForEntity(entityId)
      .then(setRows)
      .catch(() => {})
      .finally(() => setLoading(false));
  }
  useEffect(() => { refresh(); }, [entityId]);

  async function handleVerify(id: string) {
    setBusy(`verify-${id}`);
    try {
      await verifyBanking(id);
      toast.success("Banking verified.");
      refresh();
    } catch (e) {
      const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
      toast.error(`Verify failed — ${msg}`);
    } finally { setBusy(null); }
  }

  async function handleTerminate() {
    if (!terminateOpen || !terminateReason.trim()) return;
    setBusy(`terminate-${terminateOpen}`);
    try {
      await terminateBanking(terminateOpen, terminateReason);
      toast.success("Banking terminated.");
      setTerminateOpen(null);
      refresh();
    } catch (e) {
      const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
      toast.error(`Terminate failed — ${msg}`);
    } finally { setBusy(null); }
  }

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold">Banking records</h2>
        <button onClick={() => setShowAdd(true)}
                className="inline-flex items-center gap-1.5 rounded-md bg-violet-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-violet-600">
          <Plus className="h-3.5 w-3.5" /> Add banking
        </button>
      </div>

      {loading ? <p className="text-sm text-muted-foreground">Loading…</p>
        : rows.length === 0
        ? <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
            No banking records. Add one to enable batch generation.
          </p>
        : (
          <div className="overflow-x-auto rounded-lg border bg-card">
            <table className="w-full text-sm">
              <thead className="bg-muted/30 text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 text-left">Routing</th>
                  <th className="px-3 py-2 text-left">Account</th>
                  <th className="px-3 py-2 text-left">Type</th>
                  <th className="px-3 py-2 text-left">Effective</th>
                  <th className="px-3 py-2 text-left">Source</th>
                  <th className="px-3 py-2 text-left">Verified</th>
                  <th className="px-3 py-2 text-left">Status</th>
                  <th className="px-3 py-2"></th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {rows.map((b) => (
                  <tr key={b.id}>
                    <td className="px-3 py-1.5 font-mono text-xs">{b.routing_number}</td>
                    <td className="px-3 py-1.5 font-mono text-xs">****{b.account_number_last_four}</td>
                    <td className="px-3 py-1.5 text-xs">{b.account_type}</td>
                    <td className="px-3 py-1.5 text-xs">
                      {b.effective_from}
                      {b.termination_date && <span className="text-muted-foreground"> → {b.termination_date}</span>}
                    </td>
                    <td className="px-3 py-1.5 text-xs">{b.source}</td>
                    <td className="px-3 py-1.5 text-xs">
                      {b.verified_at
                        ? <span className="text-emerald-500">{new Date(b.verified_at).toLocaleDateString()}</span>
                        : <span className="text-amber-500">unverified</span>}
                    </td>
                    <td className="px-3 py-1.5 text-xs">
                      {b.is_active
                        ? <span className="text-emerald-500">active</span>
                        : <span className="text-muted-foreground">terminated</span>}
                    </td>
                    <td className="px-3 py-1.5 text-right">
                      {b.is_active && (
                        <div className="flex justify-end gap-1">
                          {!b.verified_at && (
                            <button onClick={() => handleVerify(b.id)}
                                    disabled={busy === `verify-${b.id}`}
                                    className="rounded-md border px-2 py-1 text-xs hover:bg-muted">
                              <ShieldCheck className="inline h-3 w-3" /> Verify
                            </button>
                          )}
                          <button onClick={() => setTerminateOpen(b.id)}
                                  className="rounded-md border border-rose-500/50 px-2 py-1 text-xs text-rose-600 hover:bg-rose-500/5">
                            Terminate
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

      {showAdd && (
        <AddBankingDialog entityId={entityId}
                          onClose={() => setShowAdd(false)}
                          onCreated={() => { setShowAdd(false); refresh(); }} />
      )}

      <DestructiveActionDialog
        open={!!terminateOpen}
        onOpenChange={(o) => !o && setTerminateOpen(null)}
        title="Terminate banking record"
        description="Termination prevents the banking row from being used in
        new batches. Existing batches with this banking continue to settle.
        This is logged in the change log."
        actionLabel="Terminate"
        onConfirm={handleTerminate}
        loading={busy?.startsWith("terminate-") ?? false}
        reasonRequired
        onReasonChange={setTerminateReason}
      />
    </div>
  );
}

function AddBankingDialog({
  entityId, onClose, onCreated,
}: {
  entityId: string;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [routing, setRouting] = useState("");
  const [account, setAccount] = useState("");
  const [type, setType] = useState<"checking" | "savings" | "business_checking" | "business_savings">("checking");
  const [busy, setBusy] = useState(false);

  async function handleCreate() {
    if (!routing.trim() || !account.trim()) return;
    setBusy(true);
    try {
      await createBanking({
        pay_to_entity_id: entityId,
        routing_number: routing.trim(),
        account_number: account.trim(),
        account_type: type,
      });
      toast.success("Banking record created.");
      onCreated();
    } catch (e) {
      const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
      toast.error(`Create failed — ${msg}`);
    } finally { setBusy(false); }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm"
         onClick={onClose}>
      <div className="w-full max-w-md rounded-lg border bg-card p-6 shadow-lg"
           onClick={(e) => e.stopPropagation()}>
        <h3 className="mb-3 text-base font-semibold">Add banking record</h3>
        <p className="mb-4 text-xs text-muted-foreground">
          Account number is encrypted at rest via secret_box. Routing
          number is validated against the ABA checksum (3-7-1 weighted
          mod 10) on submit.
        </p>
        <label className="mb-3 block text-xs">
          <span className="font-medium">Routing number (9 digits)</span>
          <input type="text" value={routing} onChange={(e) => setRouting(e.target.value)}
                 className="mt-1 w-full rounded-md border bg-background px-3 py-2 font-mono text-sm" />
        </label>
        <label className="mb-3 block text-xs">
          <span className="font-medium">Account number</span>
          <input type="text" value={account} onChange={(e) => setAccount(e.target.value)}
                 className="mt-1 w-full rounded-md border bg-background px-3 py-2 font-mono text-sm" />
        </label>
        <label className="mb-3 block text-xs">
          <span className="font-medium">Account type</span>
          <select value={type} onChange={(e) => setType(e.target.value as typeof type)}
                  className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm">
            <option value="checking">Checking (consumer)</option>
            <option value="savings">Savings (consumer)</option>
            <option value="business_checking">Business checking</option>
            <option value="business_savings">Business savings</option>
          </select>
        </label>
        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onClose} disabled={busy}
                  className="rounded-md border px-3 py-1.5 text-sm hover:bg-muted disabled:opacity-50">
            Cancel
          </button>
          <button onClick={handleCreate} disabled={busy || !routing || !account}
                  className="inline-flex items-center gap-1.5 rounded-md bg-violet-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-violet-600 disabled:opacity-50">
            {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            <CheckCircle2 className="h-3.5 w-3.5" /> Create
          </button>
        </div>
      </div>
    </div>
  );
}

function ChangeLogTab({ entityId }: { entityId: string }) {
  const [entries, setEntries] = useState<BankingChangeLogEntry[]>([]);
  useEffect(() => {
    listBankingChangeLog(entityId).then(setEntries).catch(() => {});
  }, [entityId]);
  // BankingChangeLogEntry shape adapts to AuditLogTimeline's AuditEntry
  // by mapping change_type → event_type.
  const adapted = entries.map((e) => ({
    id: e.id,
    event_type: e.change_type,
    occurred_at: e.occurred_at,
    actor: e.actor,
    metadata: e.metadata,
  }));
  return <AuditLogTimeline entries={adapted} />;
}
