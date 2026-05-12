import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { EmptyState } from "@/components/paysync/empty-state";

describe("EmptyState", () => {
  it("renders title only", () => {
    render(<EmptyState title="No data" />);
    expect(screen.getByText("No data")).toBeDefined();
  });

  it("renders description and actions", () => {
    render(<EmptyState
      title="Nothing here"
      description={<span>Try creating your first item.</span>}
      primaryAction={<button>Create</button>}
      secondaryAction={<button>Learn more</button>}
    />);
    expect(screen.getByText("Try creating your first item.")).toBeDefined();
    expect(screen.getByRole("button", { name: "Create" })).toBeDefined();
    expect(screen.getByRole("button", { name: "Learn more" })).toBeDefined();
  });
});
