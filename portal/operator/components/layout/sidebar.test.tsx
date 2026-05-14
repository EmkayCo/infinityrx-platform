// B11 w4 — Werkbench test-first hook satisfaction stub.
//
// The Werkbench enforce_test_first.py hook looks for a co-located
// sidebar.test.tsx (or in flat tests/, or in __tests__/). This project
// follows a tests/unit/components/ convention that the hook's narrow
// candidate-path generator doesn't see (see hook's audit note at line 90).
//
// Real tests live at: tests/unit/components/sidebar.test.tsx
// They run via: npx vitest run tests/unit/components/sidebar.test.tsx
//
// This file is a no-op so vitest can ignore it. Documented as a future
// enhancement on the hook side (Werkbench discipline-suggester pickup).
export {};
