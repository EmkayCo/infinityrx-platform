import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DataTable } from "../primitives/DataTable.js";

interface Row { id: number; name: string }

const columns = [
  { key: "id" as const, header: "ID" },
  { key: "name" as const, header: "Name" },
];

const rows: Row[] = [
  { id: 1, name: "Alice" },
  { id: 2, name: "Bob" },
];

describe("DataTable", () => {
  it("renders column headers", () => {
    render(<DataTable columns={columns} rows={rows} />);
    expect(screen.getByText("ID")).toBeDefined();
    expect(screen.getByText("Name")).toBeDefined();
  });

  it("renders a row per data entry", () => {
    render(<DataTable columns={columns} rows={rows} />);
    expect(screen.getByText("Alice")).toBeDefined();
    expect(screen.getByText("Bob")).toBeDefined();
  });

  it("renders empty state message when rows is empty", () => {
    render(<DataTable columns={columns} rows={[]} emptyMessage="No results" />);
    expect(screen.getByText("No results")).toBeDefined();
  });
});
