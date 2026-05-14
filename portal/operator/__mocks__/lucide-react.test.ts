// B11 w4 — Werkbench test-first hook satisfaction stub for the
// lucide-react test-mock. The mock file IS test infrastructure (per the
// __mocks__/ Vitest/Jest convention) but the Werkbench hook's
// EXEMPT_PATH_COMPONENTS list doesn't include __mocks__/ yet.
//
// This export-{}-only stub satisfies the hook so the mock can evolve
// alongside production icon imports. Vitest's include glob doesn't reach
// __mocks__/ so this never runs.
export {};
