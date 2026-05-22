"use client";
/**
 * /admin/paysync/uploads/[id]/configure -- Field Configuration screen.
 *
 * Shows a table: Position | Sample Value | Field Name | Type | Mandatory | PHI
 * PHI positions show *** in Sample Value and never return plaintext.
 * Save is atomic: all changes sent in one PUT request.
 */
import { useState, useCallback, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";

const DATA_TYPES = ["string", "date", "decimal", "npi", "ndc", "integer"] as const;
type DataType = (typeof DATA_TYPES)[number];

interface FieldEntry {
  position: number;
  field_name: string;
  data_type: DataType;
  is_mandatory: boolean;
  is_phi: boolean;
  sample_value: string | null;
  updated_at: string | null;
}

interface FieldConfigResponse {
  upload_id: string;
  tenant_id: string;
  fields: FieldEntry[];
  field_count: number;
}

interface SampleValuesResponse {
  upload_id: string;
  samples: Record<string, string | null>;
  field_count: number;
}

interface RowState {
  field_name: string;
  data_type: DataType;
  is_mandatory: boolean;
  is_phi: boolean;
}

async function fetchFieldConfig(id: string): Promise<FieldConfigResponse> {
  const res = await fetch(`/api/paysync/uploads/${encodeURIComponent(id)}/field-config`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error("Failed to load field config");
  return res.json() as Promise<FieldConfigResponse>;
}

async function fetchSamples(id: string): Promise<SampleValuesResponse> {
  const res = await fetch(
    `/api/paysync/uploads/${encodeURIComponent(id)}/field-config?samples=1`,
    { cache: "no-store" }
  );
  if (!res.ok) throw new Error("Failed to load sample values");
  return res.json() as Promise<SampleValuesResponse>;
}

interface SaveArgs {
  id: string;
  rows: Map<number, RowState>;
  positions: number[];
}

async function saveFieldConfig({ id, rows, positions }: SaveArgs): Promise<FieldConfigResponse> {
  const fields = positions.map((pos) => {
    const row = rows.get(pos)!;
    return {
      position: pos,
      field_name: row.field_name || `field_${pos}`,
      data_type: row.data_type,
      is_mandatory: row.is_mandatory,
      is_phi: row.is_phi,
    };
  });
  const res = await fetch(`/api/paysync/uploads/${encodeURIComponent(id)}/field-config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fields }),
  });
  if (!res.ok) throw new Error("Failed to save field config");
  return res.json() as Promise<FieldConfigResponse>;
}

/** Best-guess names for common PBM positions in the InfinityRx operator export. */
const FIELD_GUESSES: Record<number, string> = {
  1: "claim_type",        2: "auth_number",       3: "reversal_flag",
  4: "date_received",     5: "processing_date",   6: "plan_id",
  7: "group_id",          8: "member_id",          9: "person_code",
  10: "relationship_code", 11: "date_of_birth",   12: "gender_code",
  13: "pharmacy_npi",     14: "ndc",               15: "drug_name",
  16: "quantity",         17: "days_supply",       18: "date_of_service",
  19: "prescriber_npi",   20: "prescriber_name",  21: "ingredient_cost",
  22: "dispensing_fee",   23: "patient_pay",       24: "plan_pay",
  25: "other_payer_amount", 26: "net_amount",      27: "amount_billed",
};

/** Positions commonly containing PHI in PBM exports. Pre-checked as a usability hint. */
const PHI_POSITIONS = new Set([8, 9, 11, 12, 20]);

export default function FieldConfigPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params.id ?? "";
  const queryClient = useQueryClient();

  const [rows, setRows] = useState<Map<number, RowState>>(new Map());
  const [dirty, setDirty] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  const configQuery = useQuery<FieldConfigResponse, Error>({
    queryKey: ["paysync", "uploads", id, "field-config"],
    queryFn: () => fetchFieldConfig(id),
    enabled: !!id,
    staleTime: 30_000,
  });

  const samplesQuery = useQuery<SampleValuesResponse, Error>({
    queryKey: ["paysync", "uploads", id, "field-config-samples"],
    queryFn: () => fetchSamples(id),
    enabled: !!id,
    staleTime: 60_000,
  });

  // Initialise row state from saved config + sample-derived field_count
  useEffect(() => {
    const fieldCount =
      samplesQuery.data?.field_count ?? configQuery.data?.field_count ?? 0;
    if (fieldCount === 0) return;
    const savedFields = new Map<number, FieldEntry>(
      (configQuery.data?.fields ?? []).map((f) => [f.position, f])
    );
    const initialRows = new Map<number, RowState>();
    for (let pos = 1; pos <= fieldCount; pos++) {
      const saved = savedFields.get(pos);
      initialRows.set(pos, {
        field_name: saved?.field_name ?? (FIELD_GUESSES[pos] ?? `field_${pos}`),
        data_type: (saved?.data_type as DataType) ?? "string",
        is_mandatory: saved?.is_mandatory ?? false,
        is_phi: saved?.is_phi ?? PHI_POSITIONS.has(pos),
      });
    }
    setRows(initialRows);
    setDirty(false);
  }, [configQuery.data, samplesQuery.data]);

  const mutation = useMutation({
    mutationFn: (args: SaveArgs) => saveFieldConfig(args),
    onSuccess: () => {
      setDirty(false);
      setSaveError(null);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
      void queryClient.invalidateQueries({
        queryKey: ["paysync", "uploads", id, "field-config"],
      });
    },
    onError: () => setSaveError("Save failed. Please try again."),
  });

  const handleChange = useCallback(
    (pos: number, field: keyof RowState, value: string | boolean) => {
      setRows((prev) => {
        const next = new Map(prev);
        const row = next.get(pos);
        if (!row) return prev;
        next.set(pos, { ...row, [field]: value });
        return next;
      });
      setDirty(true);
      setSaveSuccess(false);
    },
    []
  );

  const handleSave = useCallback(() => {
    const positions = Array.from(rows.keys()).sort((a, b) => a - b);
    mutation.mutate({ id, rows, positions });
  }, [id, rows, mutation]);

  const isLoading = configQuery.isLoading || samplesQuery.isLoading;
  const fieldCount =
    samplesQuery.data?.field_count ?? configQuery.data?.field_count ?? 0;
  const positions = Array.from({ length: fieldCount }, (_, i) => i + 1);
  const sampleMap = samplesQuery.data?.samples ?? {};

  if (isLoading) {
    return (
      <div className="p-6">
        <p className="text-sm text-gray-500">Loading field configuration...</p>
      </div>
    );
  }

  if (configQuery.error ?? samplesQuery.error) {
    return (
      <div className="p-6">
        <p className="text-sm text-red-600" role="alert">
          Failed to load configuration. Please refresh and try again.
        </p>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <button
            onClick={() => router.push(`/admin/paysync/uploads/${id}`)}
            className="text-sm text-blue-600 hover:underline mb-1"
          >
            &larr; Back to Upload
          </button>
          <h1 className="text-xl font-semibold text-gray-900">
            Field Configuration
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Upload ID: <span className="font-mono text-xs">{id}</span>
            {fieldCount > 0 && (
              <span className="ml-3">{fieldCount} positions detected</span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {saveSuccess && (
            <span className="text-sm text-green-600 font-medium">Saved!</span>
          )}
          {saveError && (
            <span className="text-sm text-red-600">{saveError}</span>
          )}
          <button
            onClick={handleSave}
            disabled={!dirty || mutation.isPending}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {mutation.isPending ? "Saving..." : "Save Changes"}
          </button>
        </div>
      </div>

      {fieldCount === 0 && (
        <div className="rounded border border-yellow-200 bg-yellow-50 p-4 text-sm text-yellow-800">
          No raw rows captured for this upload. Upload a pipe-delimited file first.
        </div>
      )}

      {fieldCount > 0 && (
        <div className="overflow-x-auto rounded border border-gray-200">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wide w-16">
                  Pos
                </th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wide w-56">
                  Sample Value
                </th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                  Field Name
                </th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wide w-32">
                  Type
                </th>
                <th className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase tracking-wide w-24">
                  Mandatory
                </th>
                <th className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase tracking-wide w-16">
                  PHI
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {positions.map((pos) => {
                const row = rows.get(pos);
                const sample = sampleMap[String(pos)];
                const isPhi = row?.is_phi ?? false;
                const sampleDisplay = isPhi
                  ? "***"
                  : sample === null || sample === undefined
                  ? ""
                  : sample === ""
                  ? "(empty)"
                  : sample;

                return (
                  <tr key={pos} className={isPhi ? "bg-amber-50" : undefined}>
                    <td className="px-3 py-2 font-mono text-gray-700 text-xs">
                      {pos}
                    </td>
                    <td
                      className={`px-3 py-2 font-mono text-xs max-w-xs truncate ${
                        isPhi ? "text-amber-700 italic" : "text-gray-600"
                      }`}
                      title={isPhi ? "PHI -- masked" : (sample ?? "")}
                    >
                      {sampleDisplay}
                    </td>
                    <td className="px-3 py-2">
                      <input
                        type="text"
                        value={row?.field_name ?? ""}
                        onChange={(e) =>
                          handleChange(pos, "field_name", e.target.value)
                        }
                        placeholder={`field_${pos}`}
                        className="w-full border border-gray-300 rounded px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                        aria-label={`Field name for position ${pos}`}
                      />
                    </td>
                    <td className="px-3 py-2">
                      <select
                        value={row?.data_type ?? "string"}
                        onChange={(e) =>
                          handleChange(
                            pos,
                            "data_type",
                            e.target.value as DataType
                          )
                        }
                        className="w-full border border-gray-300 rounded px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                        aria-label={`Data type for position ${pos}`}
                      >
                        {DATA_TYPES.map((t) => (
                          <option key={t} value={t}>
                            {t}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="px-3 py-2 text-center">
                      <input
                        type="checkbox"
                        checked={row?.is_mandatory ?? false}
                        onChange={(e) =>
                          handleChange(pos, "is_mandatory", e.target.checked)
                        }
                        className="h-4 w-4 rounded border-gray-300 text-blue-600"
                        aria-label={`Mandatory for position ${pos}`}
                      />
                    </td>
                    <td className="px-3 py-2 text-center">
                      <input
                        type="checkbox"
                        checked={isPhi}
                        onChange={(e) =>
                          handleChange(pos, "is_phi", e.target.checked)
                        }
                        className="h-4 w-4 rounded border-amber-400 text-amber-600"
                        aria-label={`PHI flag for position ${pos}`}
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <p className="text-xs text-gray-400">
        PHI fields (amber highlight) are masked in sample values and never stored
        in plaintext. Stage 3 will enforce mandatory fields during ETL.
      </p>
    </div>
  );
}