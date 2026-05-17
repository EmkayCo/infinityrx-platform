// packages/modules/paysync/__tests__/bff/inbox.test.ts
// Tests for the real listInboxItems BFF function wired to InboxClient.
// Verifies that the stub (always returns []) is replaced with a real call.

import { describe, expect, it, vi } from "vitest";
import type { InboxItem } from "../../src/inbox/types.js";

const TENANT = "t0000000-0000-0000-0000-000000000001";
const NOW = "2026-05-16T22:00:00.000+00:00";

function makeItem(kind: InboxItem["kind"]): InboxItem {
  return {
    id: `i-${kind}`,
    kind,
    tenant_id: TENANT,
    upload_id: null,
    rbac_required: "operator",
    created_at: NOW,
    priority: "normal",
    payload: {},
  };
}

describe("listInboxItems BFF (real InboxClient wire)", () => {
  it("returns items from the InboxClient for the given role", async () => {
    const mockItems: InboxItem[] = [
      makeItem("upload_pending_review"),
      makeItem("upload_validated_awaiting_batching"),
    ];

    const mockClient = {
      list: vi.fn().mockResolvedValue(mockItems),
    };

    // Import the function under test. It must accept an InboxClient dependency.
    const { listInboxItems } = await import("../../src/bff/inbox.js");
    const result = await listInboxItems("operator", mockClient as Parameters<typeof listInboxItems>[1]);
    expect(mockClient.list).toHaveBeenCalledWith("operator");
    expect(result).toEqual(mockItems);
  });

  it("passes the role argument to InboxClient.list", async () => {
    const mockClient = {
      list: vi.fn().mockResolvedValue([]),
    };
    const { listInboxItems } = await import("../../src/bff/inbox.js");
    await listInboxItems("approver", mockClient as Parameters<typeof listInboxItems>[1]);
    expect(mockClient.list).toHaveBeenCalledWith("approver");
  });

  it("returns an empty array when the client returns no items", async () => {
    const mockClient = {
      list: vi.fn().mockResolvedValue([]),
    };
    const { listInboxItems } = await import("../../src/bff/inbox.js");
    const result = await listInboxItems("auditor", mockClient as Parameters<typeof listInboxItems>[1]);
    expect(result).toEqual([]);
  });
});
