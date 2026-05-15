import * as React from "react";
import type { BaseClient } from "@infinityrx/contract";

interface HealthResult {
  name: string;
  ok: boolean;
  latency_ms: number;
  error?: string;
}

export interface ServicesHealthProps {
  clients: BaseClient[];
  /** Poll interval in ms. Default 30000 (30s). Pass 0 to disable polling. */
  pollIntervalMs?: number;
  className?: string;
}

/**
 * Live health dashboard for all registered backend clients.
 * Renders per-service status: green/red, latency, error message.
 * Polls on mount and at pollIntervalMs intervals.
 * IMPORTANT: Omit from production builds — dev/staging only.
 */
export function ServicesHealth({ clients, pollIntervalMs = 30_000, className }: ServicesHealthProps) {
  const [results, setResults] = React.useState<HealthResult[]>([]);

  const probe = React.useCallback(async () => {
    const probed = await Promise.all(
      clients.map(async (c) => {
        try {
          const r = await c.probeHealth();
          const result: HealthResult = { name: c.name, ok: r.ok, latency_ms: r.latency_ms };
          if (r.error != null) result.error = r.error;
          return result;
        } catch (err) {
          return { name: c.name, ok: false, latency_ms: 0, error: String(err) };
        }
      }),
    );
    setResults(probed);
  }, [clients]);

  React.useEffect(() => {
    void probe();
    if (pollIntervalMs > 0) {
      const id = setInterval(() => void probe(), pollIntervalMs);
      return () => clearInterval(id);
    }
    return undefined;
  }, [probe, pollIntervalMs]);

  return (
    <div className={["irx-qa-services-health", className].filter(Boolean).join(" ")}>
      <h2 className="irx-qa-services-health__title">Services Health</h2>
      <ul className="irx-qa-services-health__list">
        {results.map((r) => (
          <li key={r.name} className="irx-qa-services-health__item">
            <span className="irx-qa-services-health__name">{r.name}</span>
            <span className={`irx-qa-services-health__status irx-qa-services-health__status--${r.ok ? "ok" : "err"}`}>
              {r.ok ? "healthy" : "unhealthy"}
            </span>
            <span className="irx-qa-services-health__latency">{r.latency_ms} ms</span>
            {!r.ok && r.error != null && (
              <span className="irx-qa-services-health__error">{r.error}</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
