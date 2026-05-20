// packages/modules/paysync/src/components/dev-only/RoleSwitcherChip.tsx
// QA-harness ONLY. Allows a developer to flip current RBAC role during
// local dev / qa-harness sessions. Per spec §6.6 this MUST NOT ship to
// production bundles. Enforcement:
//   1. Lives under dev-only/ (not exported from components/index.ts barrel)
//   2. Only reachable via paysyncComposition.qa.RoleSwitcherChip dynamic import
//      in module.config.ts (Task 5)
//   3. Plan E adds CI bundle-scan check asserting "RoleSwitcherChip" string
//      is absent from .next/static/chunks/*.js

import { useCallback, type ChangeEvent, type ReactElement } from "react";
import type { RbacRole } from "../../inbox/types.js";

const ROLES: ReadonlyArray<RbacRole> = ["operator", "approver", "auditor"];

export interface RoleSwitcherChipProps {
  readonly currentRole: RbacRole;
  readonly onRoleChange: (role: RbacRole) => void;
}

export default function RoleSwitcherChip({
  currentRole,
  onRoleChange,
}: RoleSwitcherChipProps): ReactElement {
  const handleChange = useCallback(
    (e: ChangeEvent<HTMLSelectElement>) => {
      onRoleChange(e.target.value as RbacRole);
    },
    [onRoleChange],
  );
  return (
    <label data-testid="role-switcher-chip" style={{ background: "#fef3c7", padding: "4px 8px" }}>
      QA · Role:{" "}
      <select value={currentRole} onChange={handleChange} data-testid="role-switcher-select">
        {ROLES.map((role) => (
          <option key={role} value={role}>
            {role}
          </option>
        ))}
      </select>
    </label>
  );
}
