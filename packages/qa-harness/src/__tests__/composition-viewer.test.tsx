import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { CompositionViewer } from "../composition-viewer.js";

const manifest = { modules: ["reclaimrx", "paysync", "directories"] };

describe("CompositionViewer", () => {
  it("renders a heading", () => {
    render(<CompositionViewer manifest={manifest} />);
    expect(screen.getByText(/composition/i)).toBeDefined();
  });

  it("renders each module name from the manifest", () => {
    render(<CompositionViewer manifest={manifest} />);
    expect(screen.getByText("reclaimrx")).toBeDefined();
    expect(screen.getByText("paysync")).toBeDefined();
    expect(screen.getByText("directories")).toBeDefined();
  });

  it("shows module count", () => {
    render(<CompositionViewer manifest={manifest} />);
    expect(screen.getByText(/3/)).toBeDefined();
  });

  it("renders empty state when manifest has no modules", () => {
    render(<CompositionViewer manifest={{ modules: [] }} />);
    expect(screen.getByText(/no modules/i)).toBeDefined();
  });

  it("accepts an optional instance label", () => {
    render(<CompositionViewer manifest={manifest} instanceLabel="operator-dev" />);
    expect(screen.getByText("operator-dev")).toBeDefined();
  });
});
