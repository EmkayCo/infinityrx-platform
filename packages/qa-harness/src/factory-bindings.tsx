import * as React from "react";

export interface SeedBinding {
  /** Machine key passed to the seed callback. e.g. "tenant+prescribers+claims" */
  kind: string;
  /** Human-readable button label. */
  label: string;
}

export interface FactoryBindingsProps {
  bindings: SeedBinding[];
  /** Async callback invoked with the binding kind. Should seed the dev DB. */
  seed: (kind: string) => Promise<void>;
  className?: string;
}

type SeedState = "idle" | "seeding" | "seeded" | "error";

/**
 * Renders buttons to seed safe, non-PHI fixtures into the dev DB.
 * Each button is associated with a binding kind — the host portal defines what
 * each kind seeds (e.g. "1 tenant + 10 prescribers + 5 claims").
 * IMPORTANT: Omit from production builds — dev/staging only.
 */
export function FactoryBindings({ bindings, seed, className }: FactoryBindingsProps) {
  const [states, setStates] = React.useState<Record<string, SeedState>>(
    Object.fromEntries(bindings.map((b) => [b.kind, "idle" as SeedState])),
  );

  async function handleSeed(kind: string) {
    setStates((prev) => ({ ...prev, [kind]: "seeding" }));
    try {
      await seed(kind);
      setStates((prev) => ({ ...prev, [kind]: "seeded" }));
    } catch {
      setStates((prev) => ({ ...prev, [kind]: "error" }));
    }
  }

  return (
    <div className={["irx-qa-factory", className].filter(Boolean).join(" ")}>
      <h2 className="irx-qa-factory__title">Test Data Factory</h2>
      <ul className="irx-qa-factory__list">
        {bindings.map((b) => {
          const state = states[b.kind] ?? "idle";
          return (
            <li key={b.kind} className="irx-qa-factory__item">
              <button
                type="button"
                className="irx-qa-factory__btn"
                disabled={state === "seeding"}
                onClick={() => void handleSeed(b.kind)}
              >
                {b.label}
              </button>
              {state === "seeding" && <span className="irx-qa-factory__status">Seeding…</span>}
              {state === "seeded" && <span className="irx-qa-factory__status">Seeded.</span>}
              {state === "error" && <span className="irx-qa-factory__status irx-qa-factory__status--err">Error</span>}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
