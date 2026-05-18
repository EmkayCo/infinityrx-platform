// packages/modules/directories/src/index.ts
// Public barrel for @infinityrx/module-directories.
// Plan A: search primitives and shared components.
// Plan B: browse cluster surfaces (prescribers, pharmacies, drugs, codes, pricing, exclusions).
// Plan C: ingestion console, BFF ingest proxy routes, schedule labels.
// Plans D–E will add quality dashboard, audit viewer, E2E fixtures.

export * from "./search/index.js";
export * from "./components/index.js";
export * from "./surfaces/index.js";
export * from "./ingestion/index.js";
