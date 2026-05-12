"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { FileText, Loader2, Plus, Trash2 } from "lucide-react";

import { ApiClientError } from "@shared/lib/api-client";
import {
  listExportTemplates, deleteExportTemplate, cloneExportTemplate,
  createExportTemplate, updateExportTemplate, renderTestExportTemplate,
  type ExportTemplate, type TemplateType, type TemplateFormat,
  type UpsertExportTemplateRequest,
} from "@shared/lib/paysync-api";

import { DestructiveActionDialog } from "@/components/paysync/destructive-action-dialog";

export default function ExportTemplatesPage() {
  const [rows, setRows] = useState<ExportTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [editTemplate, setEditTemplate] = useState<ExportTemplate | null>(null);
  const [showNew, setShowNew] = useState(false);
  const [deleteId, setDeleteId] = useState<string | null>(null);

  function refresh() {
    setLoading(true);
    listExportTemplates()
      .then(setRows)
      .catch((e: unknown) => {
        const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
        toast.error(`Failed to load templates — ${msg}`);
      })
      .finally(() => setLoading(false));
  }
  useEffect(() => { refresh(); }, []);

  async function handleClone(t: ExportTemplate) {
    const name = prompt(`Clone "${t.name}" as:`, `${t.name} (copy)`);
    if (!name?.trim()) return;
    try {
      await cloneExportTemplate(t.id, name.trim());
      toast.success("Template cloned.");
      refresh();
    } catch (e) {
      const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
      toast.error(`Clone failed — ${msg}`);
    }
  }

  async function handleDelete() {
    if (!deleteId) return;
    try {
      await deleteExportTemplate(deleteId);
      toast.success("Template deleted.");
      setDeleteId(null);
      refresh();
    } catch (e) {
      const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
      toast.error(`Delete failed — ${msg}`);
    }
  }

  return (
    <div className="mx-auto max-w-[1400px] p-6">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="rounded-md bg-sky-500/10 p-2">
            <FileText className="h-5 w-5 text-sky-500" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Export templates</h1>
            <p className="text-sm text-muted-foreground">
              Operator-configurable Excel/CSV/pipe templates with column
              definitions, filters, sorts, summary, and PHI tokenization.
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
            No templates yet.
          </div>
        : (
          <div className="rounded-lg border bg-card">
            <table className="w-full text-sm">
              <thead className="bg-muted/30 text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 text-left">Name</th>
                  <th className="px-3 py-2 text-left">Type</th>
                  <th className="px-3 py-2 text-left">Format</th>
                  <th className="px-3 py-2 text-right">Columns</th>
                  <th className="px-3 py-2 text-left">PHI</th>
                  <th className="px-3 py-2 text-left">Default</th>
                  <th className="px-3 py-2"></th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {rows.map((t) => (
                  <tr key={t.id}>
                    <td className="px-3 py-1.5 text-sm font-medium">{t.name}</td>
                    <td className="px-3 py-1.5 text-xs">{t.template_type}</td>
                    <td className="px-3 py-1.5 text-xs">{t.format}</td>
                    <td className="px-3 py-1.5 text-right">{t.column_definitions.length}</td>
                    <td className="px-3 py-1.5 text-xs">
                      {t.serialize_phi
                        ? <span className="text-amber-500">tokenized</span>
                        : <span className="text-muted-foreground">none</span>}
                    </td>
                    <td className="px-3 py-1.5 text-xs">{t.is_default ? "yes" : "—"}</td>
                    <td className="px-3 py-1.5 text-right">
                      <div className="flex justify-end gap-1">
                        <button onClick={() => setEditTemplate(t)}
                                className="rounded-md border px-2 py-1 text-xs hover:bg-muted">
                          Edit
                        </button>
                        <button onClick={() => handleClone(t)}
                                className="rounded-md border px-2 py-1 text-xs hover:bg-muted">
                          Clone
                        </button>
                        <button onClick={() => setDeleteId(t.id)}
                                className="rounded-md border border-rose-500/50 p-1 text-rose-600 hover:bg-rose-500/5"
                                aria-label="Delete">
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

      {(showNew || editTemplate) && (
        <TemplateEditor
          template={editTemplate}
          onClose={() => { setShowNew(false); setEditTemplate(null); }}
          onSaved={() => { setShowNew(false); setEditTemplate(null); refresh(); }}
        />
      )}

      <DestructiveActionDialog
        open={!!deleteId}
        onOpenChange={(o) => !o && setDeleteId(null)}
        title="Delete export template"
        description="Existing exports referencing this template remain
        unchanged. Future runs will fail until reconfigured."
        actionLabel="Delete template"
        onConfirm={handleDelete}
      />
    </div>
  );
}

function TemplateEditor({
  template, onClose, onSaved,
}: {
  template: ExportTemplate | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(template?.name ?? "");
  const [type, setType] = useState<TemplateType>(template?.template_type ?? "custom");
  const [format, setFormat] = useState<TemplateFormat>(template?.format ?? "xlsx");
  const [columnsJson, setColumnsJson] = useState(
    JSON.stringify(template?.column_definitions ?? [], null, 2),
  );
  const [filtersJson, setFiltersJson] = useState(
    JSON.stringify(template?.filter_definitions ?? [], null, 2),
  );
  const [sortsJson, setSortsJson] = useState(
    JSON.stringify(template?.sort_definitions ?? [], null, 2),
  );
  const [summaryJson, setSummaryJson] = useState(
    JSON.stringify(template?.summary_definitions ?? [], null, 2),
  );
  const [serializePhi, setSerializePhi] = useState(template?.serialize_phi ?? false);
  const [seed, setSeed] = useState(template?.serialization_seed ?? "");
  const [isDefault, setIsDefault] = useState(template?.is_default ?? false);
  const [busy, setBusy] = useState(false);
  const [previewOutput, setPreviewOutput] = useState<string | null>(null);

  function parseAll(): UpsertExportTemplateRequest | null {
    try {
      return {
        name: name.trim(),
        template_type: type,
        format,
        column_definitions: JSON.parse(columnsJson),
        filter_definitions: JSON.parse(filtersJson),
        sort_definitions: JSON.parse(sortsJson),
        summary_definitions: JSON.parse(summaryJson),
        serialize_phi: serializePhi,
        serialization_seed: seed || null,
        applies_to_clients: template?.applies_to_clients ?? [],
        is_default: isDefault,
      };
    } catch {
      toast.error("One of the JSON fields is malformed.");
      return null;
    }
  }

  async function handleSave() {
    const body = parseAll();
    if (!body) return;
    setBusy(true);
    try {
      if (template) {
        await updateExportTemplate(template.id, body);
        toast.success("Template updated.");
      } else {
        await createExportTemplate(body);
        toast.success("Template created.");
      }
      onSaved();
    } catch (e) {
      const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
      toast.error(`Save failed — ${msg}`);
    } finally { setBusy(false); }
  }

  async function handleRenderTest() {
    if (!template) {
      toast.error("Save the template first to test render.");
      return;
    }
    try {
      const res = await renderTestExportTemplate(template.id, 5);
      setPreviewOutput(JSON.stringify(res, null, 2));
    } catch (e) {
      const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
      toast.error(`Render test failed — ${msg}`);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm overflow-auto p-4"
         onClick={onClose}>
      <div className="my-8 w-full max-w-3xl rounded-lg border bg-card p-6 shadow-lg"
           onClick={(e) => e.stopPropagation()}>
        <h3 className="mb-4 text-base font-semibold">
          {template ? `Edit "${template.name}"` : "New export template"}
        </h3>

        <div className="mb-3 grid grid-cols-3 gap-3 text-xs">
          <label className="col-span-3">
            <span className="font-medium">Name</span>
            <input type="text" value={name} onChange={(e) => setName(e.target.value)}
                   className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm" />
          </label>
          <label>
            <span className="font-medium">Type</span>
            <select value={type} onChange={(e) => setType(e.target.value as TemplateType)}
                    className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm">
              <option value="backup_excel">Backup Excel</option>
              <option value="claims_export">Claims export</option>
              <option value="pharmacy_statement">Pharmacy statement</option>
              <option value="cycle_summary">Cycle summary</option>
              <option value="saasant">SaaSant</option>
              <option value="custom">Custom</option>
            </select>
          </label>
          <label>
            <span className="font-medium">Format</span>
            <select value={format} onChange={(e) => setFormat(e.target.value as TemplateFormat)}
                    className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm">
              <option value="xlsx">Excel</option>
              <option value="csv">CSV</option>
              <option value="pipe_delimited">Pipe-delimited</option>
            </select>
          </label>
          <label className="flex flex-col items-start">
            <span className="font-medium">Default for type</span>
            <label className="mt-2 inline-flex items-center gap-1">
              <input type="checkbox" checked={isDefault}
                     onChange={(e) => setIsDefault(e.target.checked)} />
              <span>Mark as default</span>
            </label>
          </label>
        </div>

        <JsonField label="Column definitions" value={columnsJson} onChange={setColumnsJson} />
        <JsonField label="Filter definitions" value={filtersJson} onChange={setFiltersJson} />
        <JsonField label="Sort definitions" value={sortsJson} onChange={setSortsJson} />
        <JsonField label="Summary definitions" value={summaryJson} onChange={setSummaryJson} />

        <fieldset className="mb-3 rounded-md border p-3">
          <legend className="px-1 text-xs font-medium">PHI tokenization</legend>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={serializePhi}
                   onChange={(e) => setSerializePhi(e.target.checked)} />
            <span>Tokenize PHI fields with HMAC-SHA256(seed, value)</span>
          </label>
          {serializePhi && (
            <label className="mt-2 block text-xs">
              <span className="font-medium">Tokenization seed</span>
              <input type="text" value={seed} onChange={(e) => setSeed(e.target.value)}
                     placeholder="random per-template seed"
                     className="mt-1 w-full rounded-md border bg-background px-3 py-2 font-mono text-sm" />
            </label>
          )}
        </fieldset>

        {previewOutput && (
          <details className="mb-3 rounded-md border bg-muted/30 p-2 text-xs" open>
            <summary className="cursor-pointer font-medium">Render-test preview</summary>
            <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-all font-mono text-[10px]">
              {previewOutput}
            </pre>
          </details>
        )}

        <div className="mt-4 flex items-center justify-between">
          <button onClick={handleRenderTest}
                  className="rounded-md border px-3 py-1.5 text-sm hover:bg-muted">
            Render test (5 rows)
          </button>
          <div className="flex gap-2">
            <button onClick={onClose} disabled={busy}
                    className="rounded-md border px-3 py-1.5 text-sm hover:bg-muted disabled:opacity-50">
              Cancel
            </button>
            <button onClick={handleSave} disabled={busy || !name.trim()}
                    className="inline-flex items-center gap-1.5 rounded-md bg-sky-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-sky-600 disabled:opacity-50">
              {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              Save
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function JsonField({
  label, value, onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <label className="mb-3 block text-xs">
      <span className="font-medium">{label}</span>
      <textarea value={value} onChange={(e) => onChange(e.target.value)}
                rows={4}
                className="mt-1 w-full rounded-md border bg-background px-3 py-2 font-mono text-[11px]" />
    </label>
  );
}
