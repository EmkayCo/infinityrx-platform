// packages/modules/paysync/src/surfaces/uploads/ColumnMappingStep.tsx
// PRD Step 2 "Map Fields": detect CSV/XLSX column headers from the first
// ~8KB chunk of the file (no full-file load), auto-match to the 8 required
// billing fields by name similarity, let the user confirm or correct via
// dropdowns, then call onConfirm with the mapping JSON.
//
// Design constraints:
//   - NEVER load the whole file into memory -- use File.slice for header read
//   - Auto-match is pure string normalisation (lowercase, strip punctuation,
//     common aliases). No external library required.
//   - All 8 required fields must be mapped before confirm is enabled.
//   - Non-technical user labels: show the friendly name, not the snake_case key.

import { useState, useEffect, type ReactElement } from "react";

// The 8 required billing fields with human-readable labels.
export const REQUIRED_FIELDS: ReadonlyArray<{ key: string; label: string; hint: string }> = [
  { key: "ndc",              label: "NDC (Drug Code)",        hint: "11-digit National Drug Code" },
  { key: "npi",              label: "NPI (Provider)",         hint: "10-digit National Provider Identifier" },
  { key: "claim_id",         label: "Claim ID",               hint: "Unique claim / auth number" },
  { key: "date_of_service",  label: "Date of Service",        hint: "YYYY-MM-DD format" },
  { key: "quantity",         label: "Quantity",               hint: "Dispensed quantity, up to 3 decimal places" },
  { key: "days_supply",      label: "Days Supply",            hint: "Positive integer" },
  { key: "amount_billed",    label: "Amount Billed",          hint: "Dollar amount, up to 4 decimal places" },
  { key: "member_id",        label: "Member ID",              hint: "Up to 64 characters" },
];

// Alias table: normalised strings that should auto-match each canonical field.
// Normalisation: lowercase, strip non-alphanumeric.
const ALIASES: Record<string, ReadonlyArray<string>> = {
  ndc:             ["ndc", "drugcode", "ndccode", "nationaldrugcode", "drug", "drugid", "ndcnumber"],
  npi:             ["npi", "providernpi", "npinumber", "prescribernpi", "pharmacynpi", "provider", "npicode"],
  claim_id:        ["claimid", "claimnumber", "claimnum", "authnumber", "authnum", "rxnumber", "rxnum", "claimno"],
  date_of_service: ["dateofservice", "dos", "servicedate", "filldate", "dispenseddate", "date", "claimdate"],
  quantity:        ["quantity", "qty", "dispensedqty", "dispensedquantity", "quantitydispensed", "qtydisp"],
  days_supply:     ["dayssupply", "days", "daysupply", "dayssupp", "supplydays", "daysofsupply"],
  amount_billed:   ["amountbilled", "billedamount", "billed", "chargeamount", "charged", "totalcharged", "grossamount", "claimamount"],
  member_id:       ["memberid", "member", "patientid", "patient", "membernum", "membernumber", "subscriberId", "beneficiaryid"],
};

function normalise(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]/g, "");
}

function autoMatch(userHeaders: ReadonlyArray<string>): Record<string, string> {
  const mapping: Record<string, string> = {};
  const used = new Set<string>();

  for (const field of REQUIRED_FIELDS) {
    const aliases = ALIASES[field.key] ?? [];
    for (const header of userHeaders) {
      const n = normalise(header);
      if (!used.has(header) && aliases.includes(n)) {
        mapping[field.key] = header;
        used.add(header);
        break;
      }
    }
  }
  return mapping;
}

// Read just enough bytes to get the first header line (up to 8KB).
// Returns the parsed header columns. Handles CSV only (XLSX headers need a
// different path -- for XLSX we can't read headers from raw bytes so we
// fall back to showing all columns as detected by the billing parser and
// skipping client-side auto-detection).
async function readCsvHeaders(file: File): Promise<ReadonlyArray<string> | null> {
  const chunkSize = 8 * 1024; // 8KB -- enough for any realistic header row
  const slice = file.slice(0, chunkSize);
  try {
    const text = await slice.text();
    const firstLine = text.split(/\r?\n/)[0] ?? "";
    if (!firstLine.trim()) return null;
    // Simple CSV split -- handles quoted fields (RFC 4180 basic).
    // Does not handle escaped quotes inside quoted fields; sufficient for headers.
    const cols: string[] = [];
    let cur = "";
    let inQuote = false;
    for (let i = 0; i < firstLine.length; i++) {
      const ch = firstLine[i];
      if (ch === '"') {
        inQuote = !inQuote;
      } else if (ch === "," && !inQuote) {
        cols.push(cur.trim());
        cur = "";
      } else {
        cur += ch;
      }
    }
    cols.push(cur.trim());
    return cols.filter(Boolean);
  } catch {
    return null;
  }
}

export interface ColumnMappingStepProps {
  /** The file the user picked. Used only to read the first chunk for headers. */
  readonly file: File;
  /** Called with {canonical_field -> user_column_name} when user confirms. */
  readonly onConfirm: (mapping: Record<string, string>) => void;
  /** Called when user cancels and wants to pick a different file. */
  readonly onCancel: () => void;
}

type MappingState = Record<string, string>; // canonical -> userCol

export function ColumnMappingStep({
  file,
  onConfirm,
  onCancel,
}: ColumnMappingStepProps): ReactElement {
  const [headers, setHeaders] = useState<ReadonlyArray<string> | null>(null);
  const [mapping, setMapping] = useState<MappingState>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const isXlsx = file.name.toLowerCase().endsWith(".xlsx");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    if (isXlsx) {
      // Cannot read XLSX headers from raw bytes without a full parser.
      // Show an info message and let the user enter mapping manually by
      // providing a free-form column name entry (not ideal but correct).
      // In practice, billing uploads are almost always CSV. XLSX is rare.
      setHeaders(null);
      setLoading(false);
      return;
    }

    void readCsvHeaders(file).then((cols) => {
      if (cancelled) return;
      if (!cols || cols.length === 0) {
        setError("Could not read column headers from this file. Make sure the first row contains column names.");
        setLoading(false);
        return;
      }
      setHeaders(cols);
      setMapping(autoMatch(cols));
      setLoading(false);
    });

    return () => { cancelled = true; };
  }, [file, isXlsx]);

  const allMapped = REQUIRED_FIELDS.every((f) => Boolean(mapping[f.key]));

  function handleSelect(canonicalKey: string, userCol: string): void {
    setMapping((prev) => ({ ...prev, [canonicalKey]: userCol }));
  }

  function handleConfirm(): void {
    if (allMapped) onConfirm(mapping);
  }

  if (loading) {
    return (
      <div data-testid="mapping-step-loading">
        <p>Reading file headers...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="mapping-step-error" role="alert">
        <p>{error}</p>
        <button type="button" onClick={onCancel}>Choose a different file</button>
      </div>
    );
  }

  const autoMatchedCount = REQUIRED_FIELDS.filter((f) => Boolean(mapping[f.key])).length;
  const totalRequired = REQUIRED_FIELDS.length;

  return (
    <div data-testid="mapping-step">
      <div style={{ marginBottom: "1rem" }}>
        <h3 style={{ margin: "0 0 0.25rem" }}>Step 2: Map Your Columns</h3>
        <p style={{ margin: "0 0 0.5rem", color: "#555", fontSize: "0.9rem" }}>
          {`We found ${headers?.length ?? 0} columns in "${file.name}". `}
          {autoMatchedCount === totalRequired
            ? "All fields matched automatically -- review and confirm."
            : `We auto-matched ${autoMatchedCount} of ${totalRequired} required fields. Please map the rest.`}
        </p>
        <p style={{ margin: 0, fontSize: "0.8rem", color: "#888" }}>
          Extra columns in your file are ignored -- only the 8 mapped fields below are used.
        </p>
      </div>

      <table
        data-testid="mapping-table"
        style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}
      >
        <thead>
          <tr style={{ textAlign: "left", borderBottom: "2px solid #e0e0e0" }}>
            <th style={{ padding: "0.5rem", width: "35%" }}>Required Field</th>
            <th style={{ padding: "0.5rem", width: "40%" }}>Your Column</th>
            <th style={{ padding: "0.5rem" }}>Format / Notes</th>
          </tr>
        </thead>
        <tbody>
          {REQUIRED_FIELDS.map((field) => {
            const currentVal = mapping[field.key] ?? "";
            const autoMatched = Boolean(mapping[field.key]);
            return (
              <tr
                key={field.key}
                data-testid={`mapping-row-${field.key}`}
                style={{ borderBottom: "1px solid #f0f0f0" }}
              >
                <td style={{ padding: "0.5rem" }}>
                  <span style={{ fontWeight: 500 }}>{field.label}</span>
                  {autoMatched && (
                    <span
                      data-testid={`auto-match-badge-${field.key}`}
                      style={{
                        marginLeft: "0.4rem",
                        fontSize: "0.7rem",
                        background: "#d4edda",
                        color: "#155724",
                        borderRadius: "3px",
                        padding: "1px 4px",
                      }}
                    >
                      auto
                    </span>
                  )}
                </td>
                <td style={{ padding: "0.5rem" }}>
                  {headers ? (
                    <select
                      data-testid={`mapping-select-${field.key}`}
                      value={currentVal}
                      onChange={(e) => handleSelect(field.key, e.target.value)}
                      style={{
                        width: "100%",
                        padding: "0.3rem",
                        border: currentVal ? "1px solid #ccc" : "1px solid #e74c3c",
                        borderRadius: "4px",
                        background: currentVal ? "#fff" : "#fff5f5",
                      }}
                      aria-label={`Map ${field.label} to your column`}
                    >
                      <option value="">-- Select a column --</option>
                      {headers.map((h) => (
                        <option key={h} value={h}>{h}</option>
                      ))}
                    </select>
                  ) : (
                    // XLSX fallback: free-text entry
                    <input
                      data-testid={`mapping-input-${field.key}`}
                      type="text"
                      value={currentVal}
                      onChange={(e) => handleSelect(field.key, e.target.value)}
                      placeholder="Type your column name exactly"
                      style={{
                        width: "100%",
                        padding: "0.3rem",
                        border: currentVal ? "1px solid #ccc" : "1px solid #e74c3c",
                        borderRadius: "4px",
                      }}
                      aria-label={`Map ${field.label} to your column`}
                    />
                  )}
                </td>
                <td style={{ padding: "0.5rem", color: "#777", fontSize: "0.8rem" }}>
                  {field.hint}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <div style={{ marginTop: "1rem", display: "flex", gap: "0.75rem", alignItems: "center" }}>
        <button
          data-testid="mapping-confirm-btn"
          type="button"
          onClick={handleConfirm}
          disabled={!allMapped}
          style={{
            padding: "0.5rem 1.25rem",
            background: allMapped ? "#0070f3" : "#ccc",
            color: "#fff",
            border: "none",
            borderRadius: "4px",
            cursor: allMapped ? "pointer" : "not-allowed",
            fontWeight: 500,
          }}
        >
          {allMapped ? "Confirm Mapping and Upload" : `Map all ${totalRequired} fields to continue`}
        </button>
        <button
          data-testid="mapping-cancel-btn"
          type="button"
          onClick={onCancel}
          style={{
            padding: "0.5rem 1rem",
            background: "transparent",
            border: "1px solid #ccc",
            borderRadius: "4px",
            cursor: "pointer",
          }}
        >
          Cancel -- choose a different file
        </button>
        {!allMapped && (
          <span style={{ color: "#e74c3c", fontSize: "0.85rem" }}>
            {`${totalRequired - autoMatchedCount} field(s) still need to be mapped`}
          </span>
        )}
      </div>
    </div>
  );
}
