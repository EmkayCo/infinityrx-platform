# schemas/

JSON Schemas used to validate configuration files outside the TypeScript type system.

| Schema | Validates | Authority |
|---|---|---|
| `instance-manifest.schema.json` | `infrastructure/manifests/<instance>.yml` | SD-4 §3 |

All schemas are Draft 2020-12 + Ajv strict mode (`additionalProperties: false` enforced). The validator (`packages/scripts/validate-manifest.ts`) refuses any file that fails the schema before computing transitive-closure checks.
