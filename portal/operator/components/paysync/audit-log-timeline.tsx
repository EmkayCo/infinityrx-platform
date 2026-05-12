"use client";

import { History } from "lucide-react";

export interface AuditEntry {
  id: string;
  event_type: string;
  occurred_at: string;
  actor: string | null;
  metadata: Record<string, unknown>;
}

export function AuditLogTimeline({ entries }: { entries: AuditEntry[] }) {
  if (entries.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">No audit entries yet.</p>
    );
  }
  const sorted = [...entries].sort((a, b) =>
    new Date(b.occurred_at).getTime() - new Date(a.occurred_at).getTime(),
  );
  return (
    <ol className="space-y-3">
      {sorted.map((e) => (
        <li key={e.id} className="flex gap-3 rounded-md border bg-card/50 p-3">
          <div className="rounded-md bg-muted/50 p-1.5">
            <History className="h-3.5 w-3.5 text-muted-foreground" />
          </div>
          <div className="flex-1">
            <p className="text-sm font-medium">{e.event_type}</p>
            <p className="text-[11px] text-muted-foreground">
              {new Date(e.occurred_at).toLocaleString()}
              {e.actor && ` · ${e.actor}`}
            </p>
            {Object.keys(e.metadata).length > 0 && (
              <pre className="mt-1 whitespace-pre-wrap break-all rounded bg-muted/30 p-2 font-mono text-[10px]">
                {JSON.stringify(e.metadata, null, 2)}
              </pre>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}
