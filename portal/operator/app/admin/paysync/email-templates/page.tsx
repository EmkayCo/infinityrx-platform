"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Mail, Loader2, Plus } from "lucide-react";

import { ApiClientError } from "@shared/lib/api-client";
import {
  listEmailTemplates, upsertEmailTemplate, type EmailTemplate,
} from "@shared/lib/paysync-api";

const APPLY_EVENTS = [
  "invoice_finalized", "invoice_sent", "invoice_reminder", "payment_received",
];

export default function EmailTemplatesPage() {
  const [rows, setRows] = useState<EmailTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<EmailTemplate | null>(null);
  const [showNew, setShowNew] = useState(false);

  function refresh() {
    setLoading(true);
    listEmailTemplates()
      .then(setRows)
      .catch((e: unknown) => {
        const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
        toast.error(`Failed to load templates — ${msg}`);
      })
      .finally(() => setLoading(false));
  }
  useEffect(() => { refresh(); }, []);

  return (
    <div className="mx-auto max-w-[1400px] p-6">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="rounded-md bg-sky-500/10 p-2">
            <Mail className="h-5 w-5 text-sky-500" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Email templates</h1>
            <p className="text-sm text-muted-foreground">
              Jinja2 sandboxed templates for invoice finalization /
              send / reminder / payment events. StrictUndefined
              raises on missing render context.
            </p>
          </div>
        </div>
        <button onClick={() => setShowNew(true)}
                className="inline-flex items-center gap-1.5 rounded-md bg-sky-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-sky-600">
          <Plus className="h-3.5 w-3.5" /> New template
        </button>
      </div>

      {loading ? <p className="text-sm text-muted-foreground">Loading…</p>
        : rows.length === 0
        ? <div className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">
            No email templates yet.
          </div>
        : (
          <div className="grid gap-3 md:grid-cols-2">
            {rows.map((t) => (
              <button key={t.id} onClick={() => setEditing(t)}
                      className="rounded-md border bg-card p-3 text-left hover:bg-muted/30">
                <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  {t.applies_to_event}
                  {t.is_default && <span className="ml-1 text-emerald-500">(default)</span>}
                </p>
                <p className="mt-1 truncate text-sm font-medium">{t.subject_template}</p>
                <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{t.body_text_template}</p>
              </button>
            ))}
          </div>
        )}

      {(showNew || editing) && (
        <Editor template={editing}
                onClose={() => { setShowNew(false); setEditing(null); }}
                onSaved={() => { setShowNew(false); setEditing(null); refresh(); }} />
      )}
    </div>
  );
}

function Editor({
  template, onClose, onSaved,
}: {
  template: EmailTemplate | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [event, setEvent] = useState(template?.applies_to_event ?? "invoice_finalized");
  const [subject, setSubject] = useState(template?.subject_template ?? "");
  const [bodyText, setBodyText] = useState(template?.body_text_template ?? "");
  const [bodyHtml, setBodyHtml] = useState(template?.body_html_template ?? "");
  const [isDefault, setIsDefault] = useState(template?.is_default ?? false);
  const [busy, setBusy] = useState(false);

  async function handleSave() {
    setBusy(true);
    try {
      await upsertEmailTemplate({
        applies_to_event: event,
        subject_template: subject,
        body_text_template: bodyText,
        body_html_template: bodyHtml || null,
        is_default: isDefault,
      });
      toast.success("Email template saved.");
      onSaved();
    } catch (e) {
      const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
      toast.error(`Save failed — ${msg}`);
    } finally { setBusy(false); }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm overflow-auto p-4"
         onClick={onClose}>
      <div className="my-8 w-full max-w-2xl rounded-lg border bg-card p-6 shadow-lg"
           onClick={(e) => e.stopPropagation()}>
        <h3 className="mb-4 text-base font-semibold">
          {template ? "Edit email template" : "New email template"}
        </h3>

        <div className="mb-3 grid grid-cols-2 gap-3 text-xs">
          <label>
            <span className="font-medium">Applies to event</span>
            <select value={event} onChange={(e) => setEvent(e.target.value)}
                    className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm">
              {APPLY_EVENTS.map((e) => <option key={e} value={e}>{e}</option>)}
            </select>
          </label>
          <label className="flex flex-col">
            <span className="font-medium">Default for event</span>
            <label className="mt-2 inline-flex items-center gap-1 text-sm">
              <input type="checkbox" checked={isDefault}
                     onChange={(e) => setIsDefault(e.target.checked)} />
              <span>Mark default</span>
            </label>
          </label>
        </div>

        <label className="mb-3 block text-xs">
          <span className="font-medium">Subject template</span>
          <input type="text" value={subject} onChange={(e) => setSubject(e.target.value)}
                 placeholder="Invoice {{ invoice_number }} from {{ company_name }}"
                 className="mt-1 w-full rounded-md border bg-background px-3 py-2 font-mono text-sm" />
        </label>

        <label className="mb-3 block text-xs">
          <span className="font-medium">Body (text)</span>
          <textarea value={bodyText} onChange={(e) => setBodyText(e.target.value)} rows={8}
                    placeholder="Hello {{ bill_to_name }},&#10;&#10;Invoice {{ invoice_number }} for ${{ total_amount }} is attached."
                    className="mt-1 w-full rounded-md border bg-background px-3 py-2 font-mono text-xs" />
        </label>

        <label className="mb-3 block text-xs">
          <span className="font-medium">Body (HTML, optional)</span>
          <textarea value={bodyHtml} onChange={(e) => setBodyHtml(e.target.value)} rows={6}
                    className="mt-1 w-full rounded-md border bg-background px-3 py-2 font-mono text-xs" />
        </label>

        <details className="mb-3 rounded-md border bg-muted/30 p-3 text-xs">
          <summary className="cursor-pointer font-medium">Available variables</summary>
          <ul className="mt-2 space-y-0.5 font-mono">
            <li>invoice_number</li>
            <li>invoice_date / due_date</li>
            <li>total_amount / paid_amount</li>
            <li>bill_to_name</li>
            <li>cycle_label</li>
            <li>company_name</li>
            <li>is_resend</li>
          </ul>
        </details>

        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onClose} disabled={busy}
                  className="rounded-md border px-3 py-1.5 text-sm hover:bg-muted disabled:opacity-50">
            Cancel
          </button>
          <button onClick={handleSave} disabled={busy || !subject.trim() || !bodyText.trim()}
                  className="inline-flex items-center gap-1.5 rounded-md bg-sky-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-sky-600 disabled:opacity-50">
            {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            Save
          </button>
        </div>
      </div>
    </div>
  );
}
