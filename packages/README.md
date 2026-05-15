# packages/

SP-0 workspace root for shared TypeScript packages.

| Package | Plan that adds it | Purpose |
|---|---|---|
| `packages/contract` | Plan B | Typed backend clients, error envelope, cache policy types |
| `packages/auth` | Plan B | Canonical auth/JWT contract per SD-1 (`b876c3b`) |
| `packages/ui` | Plan C | Shared design system (Radix/shadcn primitives) |
| `packages/qa-harness` | Plan C | Dev-mode harness (services-health, mock toggle, factories) |
| `packages/shell` | Plan C | Thin Next.js host; module registration + mounting + generated composition artifacts |
| `packages/modules/<name>` | Plan D + SP-1+ | One package per product module; SP-0 ships ReclaimRx as the reference |

All packages here are framework-agnostic per SD-2 (`14d847a`) — zero `next/*` imports. Next.js usage lives ONLY in `portal/operator/app/`.
