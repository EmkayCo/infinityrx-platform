import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import * as React from "react";
import { DndContext } from "@dnd-kit/core";
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { DragHandle } from "../dnd/DragHandle.js";

// DragHandle must be rendered inside a dnd-kit context to function correctly
function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <DndContext>
      <SortableContext items={["item-1"]} strategy={verticalListSortingStrategy}>
        {children}
      </SortableContext>
    </DndContext>
  );
}

describe("DragHandle", () => {
  it("renders a drag handle element", () => {
    render(
      <Wrapper>
        <DragHandle id="item-1" aria-label="Drag to reorder" />
      </Wrapper>,
    );
    expect(screen.getByRole("button", { name: "Drag to reorder" })).toBeDefined();
  });

  it("has the irx-drag-handle class", () => {
    const { container } = render(
      <Wrapper>
        <DragHandle id="item-1" aria-label="Drag" />
      </Wrapper>,
    );
    expect(container.querySelector(".irx-drag-handle")).toBeDefined();
  });

  it("accepts a custom className", () => {
    const { container } = render(
      <Wrapper>
        <DragHandle id="item-1" aria-label="Drag" className="my-handle" />
      </Wrapper>,
    );
    expect((container.querySelector(".irx-drag-handle") as HTMLElement)?.className).toContain("my-handle");
  });
});
