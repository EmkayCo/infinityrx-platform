// packages/modules/paysync/src/components/index.ts
// Public barrel for module-local primitives.
// The dev-only/ subfolder is intentionally excluded — anything under
// dev-only/ is reachable only via paysyncComposition.qa in module.config.ts
// and tree-shakes from production bundles per spec §6.6. A commit-hook grep
// asserts no dev-only symbol leaks into this file's exports.

export { MoneyDisplay, type MoneyDisplayProps } from "./MoneyDisplay.js";
export { MoneyInput, type MoneyInputProps } from "./MoneyInput.js";
export { RbacGate, type RbacGateProps } from "./RbacGate.js";
export { ProvenanceBreadcrumb, type ProvenanceBreadcrumbProps, type ProvenanceLink } from "./ProvenanceBreadcrumb.js";
export { HashChainBadge, type HashChainBadgeProps } from "./HashChainBadge.js";
