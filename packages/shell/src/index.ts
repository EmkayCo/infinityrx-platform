// Public surface of @infinityrx/shell.

export type { UserIdentity, SessionUser } from "./auth/types.js";
export { getSessionUser } from "./auth/get-session-user.js";
// Component prop types — exported so consumers can type their wrappers
// without reaching into src/ paths directly (CONCERN 2 closure).
export type { RequireAuthProps } from "./auth/require-auth.js";
export { RequireAuth } from "./auth/require-auth.js";
export type { RequireRoleProps } from "./auth/require-role.js";
export { RequireRole } from "./auth/require-role.js";

export type { NavEntry, InstanceManifestShape } from "./shell/nav-types.js";
export { ModuleNav } from "./shell/module-nav.js";
export type { AppShellMountProps } from "./shell/app-shell-mount.js";
export { AppShellMount } from "./shell/app-shell-mount.js";

export type { QaMode } from "./qa/qa-mode-cookie.js";
export { QA_MODE_COOKIE, parseQaMode } from "./qa/qa-mode-cookie.js";
export { QA_MODE_HEADER, applyQaModeMiddleware } from "./qa/qa-mode-middleware.js";
export { SHELL_MIDDLEWARE_MATCHER } from "./middleware.js";

export type { InspectorEntry } from "./qa/inspector/types.js";
export type { InspectorPanelProps } from "./qa/inspector/inspector-panel.js";
export { wrapFetch } from "./qa/inspector/wrap-fetch.js";
export { $inspectorEntries, addEntry, clearEntries } from "./qa/inspector/inspector-store.js";
export { InspectorPanel } from "./qa/inspector/inspector-panel.js";

// QA Harness route page components (portals mount these at app/qa-harness/...)
// Prop types exported so portals can type their mounting wrappers.
export type { QaHarnessPageProps } from "./routes/qa-harness/page.js";
export { QaHarnessPage } from "./routes/qa-harness/page.js";
export { CompositionPage } from "./routes/qa-harness/composition/page.js";
export type { MockTogglePageProps } from "./routes/qa-harness/mock-toggle/page.js";
export { MockTogglePage } from "./routes/qa-harness/mock-toggle/page.js";
export type { FactoryPageProps } from "./routes/qa-harness/factory/page.js";
export { FactoryPage } from "./routes/qa-harness/factory/page.js";
export { CorrelationPage } from "./routes/qa-harness/correlation/page.js";
