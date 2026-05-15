import * as React from "react";
import type { BaseClient } from "@infinityrx/contract";

export type ClientMode = "real" | "mock";

export interface MockToggleProps {
  clients: BaseClient[];
  onToggle: (name: string, mode: ClientMode) => void;
  initialModes?: Record<string, ClientMode>;
  className?: string;
}

/**
 * Per-client real/mock toggle. Lets QA engineers switch any backend client
 * between its real and mock implementation at runtime without redeploying.
 * IMPORTANT: Omit from production builds — dev/staging only.
 */
export function MockToggle({ clients, onToggle, initialModes, className }: MockToggleProps) {
  const [modes, setModes] = React.useState<Record<string, ClientMode>>(
    initialModes ?? Object.fromEntries(clients.map((c) => [c.name, "real" as ClientMode])),
  );

  function toggle(name: string, mode: ClientMode) {
    setModes((prev) => ({ ...prev, [name]: mode }));
    onToggle(name, mode);
  }

  return (
    <div className={["irx-qa-mock-toggle", className].filter(Boolean).join(" ")}>
      <h2 className="irx-qa-mock-toggle__title">Mock / Real Toggle</h2>
      <ul className="irx-qa-mock-toggle__list">
        {clients.map((c) => (
          <li key={c.name} className="irx-qa-mock-toggle__item">
            <span className="irx-qa-mock-toggle__name">{c.name}</span>
            <span className="irx-qa-mock-toggle__current">
              {modes[c.name] ?? "real"}
            </span>
            <button
              type="button"
              aria-label={`Switch ${c.name} to real`}
              className="irx-qa-mock-toggle__btn irx-qa-mock-toggle__btn--real"
              onClick={() => toggle(c.name, "real")}
            >
              real
            </button>
            <button
              type="button"
              aria-label={`Switch ${c.name} to mock`}
              className="irx-qa-mock-toggle__btn irx-qa-mock-toggle__btn--mock"
              onClick={() => toggle(c.name, "mock")}
            >
              mock
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
