# infrastructure/manifests/

Per-customer instance manifests. One YAML file per customer-instance, validated against `schemas/instance-manifest.schema.json` by `packages/scripts/validate-manifest.ts`.

| File | Purpose |
|---|---|
| `operator-dev.yml` | Dev / reference full composition. Modules list grows in Plan D as packages/modules/* are added. |
| `example-reclaimrx-standalone.yml` | Reference shape for a single-module customer. Not auto-deployed. |

Plan A validates that both files pass the schema. Plans B/C/D extend `operator-dev.yml` as new modules ship.

Manifest authority is SD-4 §3 (`docs/superpowers/specs/2026-05-15-sp0-decision-spike-composition.md`).
