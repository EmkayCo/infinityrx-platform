import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";

import {
  TableSkeleton, KpiRowSkeleton, CardGridSkeleton,
} from "@/components/paysync/loading-skeleton";

describe("loading skeletons", () => {
  it("TableSkeleton renders aria-busy", () => {
    const { container } = render(<TableSkeleton rows={5} />);
    const root = container.querySelector('[aria-busy="true"]');
    expect(root).not.toBeNull();
    expect(root?.getAttribute("aria-label")).toBe("Loading");
  });

  it("KpiRowSkeleton renders requested count", () => {
    const { container } = render(<KpiRowSkeleton count={4} />);
    const cards = container.querySelectorAll(".rounded-lg.border.bg-card.p-3");
    expect(cards.length).toBe(4);
  });

  it("CardGridSkeleton renders requested count", () => {
    const { container } = render(<CardGridSkeleton count={3} />);
    const cards = container.querySelectorAll(".rounded-lg.border.bg-card.p-4");
    expect(cards.length).toBe(3);
  });
});
