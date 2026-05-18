// src/surfaces/prescribers/PrescriberMonitoringPanel.tsx
// Read-only list of prescriber monitoring alerts from
// GET /api/v1/prescribers/monitoring/alerts (router.py line 344).
// Alert acknowledgment is NOT in SP-2 scope — no acknowledge button rendered.
import React from "react";
import { useQuery } from "@tanstack/react-query";

export interface MonitoringAlert {
  alert_id: string;
  alert_type: string;
  severity: string;
  created_at: string;
  description: string;
}

interface AlertsResponse {
  alerts: MonitoringAlert[];
}

export interface PrescriberMonitoringPanelProps {
  npi: string;
  prescriberDirectoryUrl?: string;
}

export function PrescriberMonitoringPanel({ npi, prescriberDirectoryUrl = "http://localhost:8010" }: PrescriberMonitoringPanelProps) {
  const { data, isLoading } = useQuery<MonitoringAlert[]>({
    queryKey: ["prescriber-alerts", npi],
    queryFn: async () => {
      const url = `${prescriberDirectoryUrl}/api/v1/prescribers/monitoring/alerts?npi=${encodeURIComponent(npi)}`;
      const resp = await fetch(url);
      if (!resp.ok) throw new Error(`monitoring alerts failed: ${resp.status}`);
      const body = (await resp.json()) as AlertsResponse;
      return body.alerts ?? [];
    },
    staleTime: 60_000,
  });

  const alerts = data ?? [];

  return (
    <div data-testid="monitoring-panel">
      <h4>Monitoring Alerts</h4>
      {isLoading && <p data-testid="alerts-loading">Loading alerts...</p>}
      {!isLoading && alerts.length === 0 && (
        <p data-testid="no-alerts">No monitoring alerts.</p>
      )}
      <ul data-testid="alerts-list">
        {alerts.map((alert) => (
          <li key={alert.alert_id} data-testid="alert-row">
            <span data-testid="alert-type">{alert.alert_type}</span>
            {" — "}
            <span data-testid="alert-severity">{alert.severity}</span>
            {": "}
            <span data-testid="alert-description">{alert.description}</span>
            {/* No acknowledge button — out of SP-2 scope per spec §3 */}
          </li>
        ))}
      </ul>
    </div>
  );
}
