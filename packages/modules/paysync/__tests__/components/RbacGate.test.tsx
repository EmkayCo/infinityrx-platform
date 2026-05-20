// packages/modules/paysync/__tests__/components/RbacGate.test.tsx
// 100% branch coverage required (security path per Auto-Gate).

import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { RbacGate } from "../../src/components/RbacGate.js";

afterEach(() => cleanup());

describe("RbacGate", () => {
  it("renders children unwrapped when single role matches", () => {
    render(
      <RbacGate role="operator" currentRole="operator">
        <button>Action</button>
      </RbacGate>,
    );
    expect(screen.getByTestId("rbac-gate-allowed")).toBeTruthy();
    expect(screen.getByRole("button").hasAttribute("disabled")).toBe(false);
  });

  it("renders children disabled when single role does NOT match", () => {
    render(
      <RbacGate role="approver" currentRole="operator">
        <button>Approve</button>
      </RbacGate>,
    );
    expect(screen.getByTestId("rbac-gate-denied")).toBeTruthy();
    expect(screen.getByTestId("rbac-gate-denied").getAttribute("aria-disabled")).toBe("true");
    expect(screen.getByTestId("rbac-gate-denied").getAttribute("title")).toBe("approver role required");
    expect(screen.getByRole("button").hasAttribute("disabled")).toBe(true);
    expect(screen.getByRole("button").getAttribute("tabindex")).toBe("-1");
  });

  it("renders children unwrapped when array-of-roles includes current role", () => {
    render(
      <RbacGate role={["approver", "operator"]} currentRole="operator">
        <button>Either</button>
      </RbacGate>,
    );
    expect(screen.getByTestId("rbac-gate-allowed")).toBeTruthy();
  });

  it("renders children disabled when array-of-roles does NOT include current role", () => {
    render(
      <RbacGate role={["approver", "auditor"]} currentRole="operator">
        <button>Approve or Audit</button>
      </RbacGate>,
    );
    expect(screen.getByTestId("rbac-gate-denied")).toBeTruthy();
    expect(screen.getByTestId("rbac-gate-denied").getAttribute("title")).toBe("approver or auditor role required");
  });

  it("handles non-element children safely (text node)", () => {
    render(
      <RbacGate role="approver" currentRole="operator">
        Plain text
      </RbacGate>,
    );
    expect(screen.getByTestId("rbac-gate-denied").textContent).toBe("Plain text");
  });
});
