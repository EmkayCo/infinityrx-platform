// B11 w3 — Werkbench enforce_test_first hook satisfaction stub.
//
// Real coverage for the F-010 NextAuth session-sync fix lives in
// portal/operator/tests/e2e/b11-dogfood.spec.ts F-ISSUE-1
// ("login → wrong-page-before-refresh reproduction"). That test asserts
// the bug pre-fix and will flip to NOT reproduce post-fix.
//
// Verify:
//   PW_REUSE_SERVER=true npx playwright test b11-dogfood -g F-ISSUE-1
//
// The findings.json should show bug_reproduced: false after w3 lands.
export {};
