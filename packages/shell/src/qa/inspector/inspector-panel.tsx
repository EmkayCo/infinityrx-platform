"use client";
import { useStore } from "@nanostores/react";
import { useState } from "react";
import { $inspectorEntries, clearEntries } from "./inspector-store.js";
import type { InspectorEntry } from "./types.js";

/**
 * InspectorPanel takes no props — it reads state directly from the
 * $inspectorEntries nanostores atom. Type alias (not interface) avoids
 * @typescript-eslint/no-empty-object-type lint error (same pattern as
 * packages/ui Input.tsx). Re-exported from index.ts for consumer typing.
 */
export type InspectorPanelProps = Record<string, never>;

/**
 * Client-side slide-out inspector panel.
 * Subscribes to $inspectorEntries and renders a table of captured requests.
 * Only rendered in non-production builds (gated by the parent route/layout).
 */
export function InspectorPanel(_props: InspectorPanelProps = {} as InspectorPanelProps) {
  const entries = useStore($inspectorEntries);
  const [open, setOpen] = useState(false);

  if (!open) {
    return (
      <button
        style={{ position: "fixed", bottom: "1rem", right: "1rem", zIndex: 9999 }}
        onClick={() => setOpen(true)}
        aria-label="Open request inspector"
      >
        Inspector ({entries.length})
      </button>
    );
  }

  return (
    <aside
      role="complementary"
      aria-label="Request/response inspector"
      style={{
        position: "fixed",
        bottom: 0,
        right: 0,
        width: "480px",
        height: "60vh",
        overflowY: "auto",
        background: "#1a1a1a",
        color: "#f0f0f0",
        zIndex: 9999,
        padding: "1rem",
        fontFamily: "monospace",
        fontSize: "12px",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.5rem" }}>
        <strong>Request Inspector ({entries.length})</strong>
        <span>
          <button onClick={() => clearEntries()} style={{ marginRight: "0.5rem" }}>
            Clear
          </button>
          <button onClick={() => setOpen(false)} aria-label="Close inspector">
            ✕
          </button>
        </span>
      </div>
      {entries.length === 0 && <p>No requests captured yet.</p>}
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th>Method</th>
            <th>Route</th>
            <th>Status</th>
            <th>ms</th>
            <th>Cache</th>
            <th>corrId</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e: InspectorEntry) => (
            <InspectorRow key={e.id} entry={e} />
          ))}
        </tbody>
      </table>
    </aside>
  );
}

function InspectorRow({ entry }: { entry: InspectorEntry }) {
  const [expanded, setExpanded] = useState(false);
  const route = (() => {
    try { return new URL(entry.url).pathname; } catch { return entry.url; }
  })();
  const statusColor = entry.status >= 400 ? "#ff6b6b" : entry.status === 0 ? "#ffa500" : "#69db7c";

  return (
    <>
      <tr
        onClick={() => setExpanded((p) => !p)}
        style={{ cursor: "pointer", borderBottom: "1px solid #333" }}
      >
        <td>{entry.method}</td>
        <td title={entry.url}>{route.slice(0, 30)}</td>
        <td style={{ color: statusColor }}>{entry.status || "ERR"}</td>
        <td>{entry.latencyMs}</td>
        <td>{entry.cacheHit ? "HIT" : "—"}</td>
        <td title={entry.correlationId}>{entry.correlationId?.slice(0, 8) ?? "—"}</td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={6}>
            <pre style={{ whiteSpace: "pre-wrap", wordBreak: "break-all" }}>
              {JSON.stringify({ request: entry.requestBody, response: entry.responseBody }, null, 2)}
            </pre>
          </td>
        </tr>
      )}
    </>
  );
}
