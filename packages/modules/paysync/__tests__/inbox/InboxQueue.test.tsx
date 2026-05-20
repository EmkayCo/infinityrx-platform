// packages/modules/paysync/__tests__/inbox/InboxQueue.test.tsx
// Render + filter-by-role + empty-state tests for InboxQueue.

import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { InboxQueue } from "../../src/inbox/InboxQueue.js";
import type { InboxItem } from "../../src/inbox/types.js";

const TENANT = "00000000-0000-0000-0000-000000000001";
const NOW = "2026-05-16T22:00:00.000Z";

function makeItem(partial: Partial<InboxItem> & Pick<InboxItem, "id" | "kind" | "rbac_required">): InboxItem {
  return {
    tenant_id: TENANT,
    upload_id: null,
    created_at: NOW,
    priority: "normal",
    payload: {},
    ...partial,
  };
}

const items: InboxItem[] = [
  makeItem({ id: "i1", kind: "upload_pending_review", rbac_required: "operator" }),
  makeItem({ id: "i2", kind: "batch_drafted", rbac_required: "approver" }),
  makeItem({ id: "i3", kind: "journal_periodic_review", rbac_required: "auditor" }),
];

// useVirtualizer needs measurable scroll-container dimensions. happy-dom
// returns 0 by default, so the virtualizer renders zero rows even when items
// are present. Patch the prototype to give every element a usable viewport
// for the duration of the InboxQueue render tests.
let originalClientHeight: PropertyDescriptor | undefined;
let originalClientWidth: PropertyDescriptor | undefined;
let originalGetBoundingClientRect: typeof HTMLElement.prototype.getBoundingClientRect;

beforeEach(() => {
  originalClientHeight = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "clientHeight");
  originalClientWidth = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "clientWidth");
  originalGetBoundingClientRect = HTMLElement.prototype.getBoundingClientRect;

  Object.defineProperty(HTMLElement.prototype, "clientHeight", { configurable: true, value: 800 });
  Object.defineProperty(HTMLElement.prototype, "clientWidth", { configurable: true, value: 600 });
  HTMLElement.prototype.getBoundingClientRect = function (): DOMRect {
    return {
      width: 600,
      height: 800,
      top: 0,
      left: 0,
      bottom: 800,
      right: 600,
      x: 0,
      y: 0,
      toJSON() { return {}; },
    } as DOMRect;
  };
});

afterEach(() => {
  // Vitest + @testing-library/react v16 do not auto-cleanup mounted trees.
  // Without explicit cleanup() each render leaks into document.body and the
  // next test's queries see stale rows from prior assertions.
  cleanup();
  if (originalClientHeight) {
    Object.defineProperty(HTMLElement.prototype, "clientHeight", originalClientHeight);
  }
  if (originalClientWidth) {
    Object.defineProperty(HTMLElement.prototype, "clientWidth", originalClientWidth);
  }
  HTMLElement.prototype.getBoundingClientRect = originalGetBoundingClientRect;
});

describe("InboxQueue", () => {
  it("renders empty state when there are no items at all", () => {
    render(<InboxQueue items={[]} role="operator" />);
    expect(screen.getByTestId("inbox-queue-empty")).toBeTruthy();
    expect(screen.queryByTestId("inbox-queue")).toBeNull();
  });

  it("renders empty state when no items match the active role", () => {
    const noOps: InboxItem[] = [
      makeItem({ id: "i2", kind: "batch_drafted", rbac_required: "approver" }),
      makeItem({ id: "i3", kind: "journal_periodic_review", rbac_required: "auditor" }),
    ];
    render(<InboxQueue items={noOps} role="operator" />);
    expect(screen.getByTestId("inbox-queue-empty")).toBeTruthy();
  });

  it("shows exactly the operator row when role=operator", () => {
    render(<InboxQueue items={items} role="operator" />);
    expect(screen.getByTestId("inbox-queue")).toBeTruthy();
    expect(screen.getByTestId("inbox-row-upload_pending_review")).toBeTruthy();
    expect(screen.queryByTestId("inbox-row-batch_drafted")).toBeNull();
    expect(screen.queryByTestId("inbox-row-journal_periodic_review")).toBeNull();
  });

  it("shows exactly the approver row when role=approver", () => {
    render(<InboxQueue items={items} role="approver" />);
    expect(screen.getByTestId("inbox-row-batch_drafted")).toBeTruthy();
    expect(screen.queryByTestId("inbox-row-upload_pending_review")).toBeNull();
    expect(screen.queryByTestId("inbox-row-journal_periodic_review")).toBeNull();
  });

  it("shows exactly the auditor row when role=auditor", () => {
    render(<InboxQueue items={items} role="auditor" />);
    expect(screen.getByTestId("inbox-row-journal_periodic_review")).toBeTruthy();
    expect(screen.queryByTestId("inbox-row-upload_pending_review")).toBeNull();
    expect(screen.queryByTestId("inbox-row-batch_drafted")).toBeNull();
  });
});
