// packages/modules/paysync/src/components/RbacGate.tsx
// Gates an action by RBAC role. Per spec §5.4: when denied, renders the
// children disabled (visible, aria-disabled, pointer-events-none) — never
// hides. This makes the UI legible to all roles ("you would do X here, but
// you lack the role") while preventing the action.

import { Children, cloneElement, isValidElement, type ReactElement, type ReactNode } from "react";
import type { RbacRole } from "../inbox/types.js";

export interface RbacGateProps {
  /** Required role (or any of an array of roles). */
  readonly role: RbacRole | ReadonlyArray<RbacRole>;
  /** The user's current role. */
  readonly currentRole: RbacRole;
  /** The action UI to gate. */
  readonly children: ReactNode;
}

export function RbacGate({ role, currentRole, children }: RbacGateProps): ReactElement {
  const allowedRoles: ReadonlyArray<RbacRole> = Array.isArray(role) ? role : [role as RbacRole];
  const allowed = allowedRoles.includes(currentRole);

  if (allowed) {
    return (
      <span data-testid="rbac-gate-allowed">
        {children}
      </span>
    );
  }

  const requiredLabel = allowedRoles.join(" or ");
  return (
    <span
      data-testid="rbac-gate-denied"
      aria-disabled="true"
      title={`${requiredLabel} role required`}
      style={{ pointerEvents: "none", opacity: 0.5 }}
    >
      {Children.map(children, (child) => {
        if (isValidElement<{ disabled?: boolean; tabIndex?: number }>(child)) {
          return cloneElement(child, { disabled: true, tabIndex: -1 });
        }
        return child;
      })}
    </span>
  );
}
