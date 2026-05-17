// packages/modules/paysync/src/surfaces/setup/CycleSchedulesPage.tsx
// Setup page for billing cycle auto-open/close schedules.
// Save action is Approver-only per spec §5.4.
// TODO(Plan-F): wire onSave to POST /api/paysync/setup/cycle-schedules.

import type { ReactElement } from "react";
import { RbacGate } from "../../components/RbacGate.js";
import type { RbacRole } from "../../inbox/types.js";

export type CycleFrequency = "monthly" | "quarterly" | "custom";

export interface CycleSchedule {
  readonly id: string;
  readonly tenant_id: string;
  readonly name: string;
  readonly frequency: CycleFrequency;
  readonly close_day: number;
  readonly open_day: number;
  readonly active: boolean;
  readonly created_at: string;
}

export interface CycleSchedulesPageProps {
  readonly schedules: ReadonlyArray<CycleSchedule>;
  readonly isLoading: boolean;
  readonly error: string | null;
  readonly currentRole: RbacRole;
  readonly onSave: (data: Omit<CycleSchedule, "id" | "tenant_id" | "created_at">) => void;
}

export function CycleSchedulesPage({
  schedules,
  isLoading,
  error,
  currentRole,
  onSave,
}: CycleSchedulesPageProps): ReactElement {
  if (isLoading) {
    return (
      <div data-testid="cycle-schedules-page">
        <div data-testid="cycle-schedules-loading" role="status" aria-label="Loading cycle schedules">
          Loading cycle schedules...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="cycle-schedules-page">
        <div data-testid="cycle-schedules-error" role="alert">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div data-testid="cycle-schedules-page">
      <h1>Cycle Schedules</h1>
      <p>Set automated billing cycle open and close schedules. Save requires Approver role.</p>

      {schedules.length > 0 && (
        <table aria-label="Cycle schedules">
          <thead>
            <tr>
              <th scope="col">Name</th>
              <th scope="col">Frequency</th>
              <th scope="col">Open Day</th>
              <th scope="col">Close Day</th>
              <th scope="col">Active</th>
            </tr>
          </thead>
          <tbody>
            {schedules.map((s) => (
              <tr key={s.id} data-testid="cycle-schedule-row">
                <td>{s.name}</td>
                <td>{s.frequency}</td>
                <td>{s.open_day}</td>
                <td>{s.close_day}</td>
                <td>{s.active ? "Yes" : "No"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <RbacGate role="approver" currentRole={currentRole}>
        <button
          type="button"
          data-testid="cycle-schedules-save-button"
          onClick={() =>
            onSave({
              name: "",
              frequency: "monthly",
              close_day: 25,
              open_day: 1,
              active: true,
            })
          }
        >
          Add Schedule
        </button>
      </RbacGate>
    </div>
  );
}
