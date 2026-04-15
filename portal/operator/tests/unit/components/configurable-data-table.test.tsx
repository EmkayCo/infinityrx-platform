import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ConfigurableDataTable, type Column } from "@/components/ui/configurable-data-table";

interface Row {
  id: string;
  name: string;
  amount: number;
  status: string;
}

const COLUMNS: Column<Row>[] = [
  { id: "name", header: "Name", accessor: (r) => r.name, pinned: true, defaultVisible: true },
  { id: "amount", header: "Amount", accessor: (r) => r.amount, format: "currency", defaultVisible: true, align: "right" },
  { id: "status", header: "Status", accessor: (r) => r.status, format: "status", defaultVisible: true },
  { id: "hidden-by-default", header: "Hidden", accessor: (r) => r.id, defaultVisible: false },
];

const DATA: Row[] = [
  { id: "1", name: "Alpha", amount: 100, status: "active" },
  { id: "2", name: "Beta", amount: 50, status: "reversed" },
  { id: "3", name: "Gamma", amount: 200, status: "active" },
];

beforeEach(() => {
  localStorage.clear();
});

describe("ConfigurableDataTable", () => {
  it("renders header and visible row cells", () => {
    render(
      <ConfigurableDataTable
        tableId="test-1"
        columns={COLUMNS}
        data={DATA}
        exportable={false}
        searchable={false}
      />,
    );
    expect(screen.getByText("Name")).toBeDefined();
    expect(screen.getByText("Amount")).toBeDefined();
    expect(screen.getByText("Alpha")).toBeDefined();
    expect(screen.getByText("$100.00")).toBeDefined();
  });

  it("hides columns that default to not visible", () => {
    render(
      <ConfigurableDataTable
        tableId="test-2"
        columns={COLUMNS}
        data={DATA}
        exportable={false}
        searchable={false}
      />,
    );
    expect(screen.queryByText("Hidden")).toBeNull();
  });

  it("sorts when header is clicked", () => {
    render(
      <ConfigurableDataTable
        tableId="test-3"
        columns={COLUMNS}
        data={DATA}
        exportable={false}
        searchable={false}
      />,
    );
    const amountHeader = screen.getByRole("button", { name: /^Amount/ });
    fireEvent.click(amountHeader); // asc
    const rowsAsc = screen.getAllByRole("row").slice(1);
    expect(rowsAsc[0].textContent).toContain("Beta");
    fireEvent.click(amountHeader); // desc
    const rowsDesc = screen.getAllByRole("row").slice(1);
    expect(rowsDesc[0].textContent).toContain("Gamma");
  });

  it("fires onRowClick with the clicked row", () => {
    const onClick = vi.fn();
    render(
      <ConfigurableDataTable
        tableId="test-4"
        columns={COLUMNS}
        data={DATA}
        exportable={false}
        searchable={false}
        onRowClick={onClick}
      />,
    );
    fireEvent.click(screen.getByText("Alpha"));
    expect(onClick).toHaveBeenCalledWith(DATA[0]);
  });

  it("persists column visibility in localStorage", () => {
    const tableId = "persistence-test";
    const { unmount } = render(
      <ConfigurableDataTable
        tableId={tableId}
        columns={COLUMNS}
        data={DATA}
        exportable={false}
        searchable={false}
      />,
    );

    // Open column menu and toggle off "Amount"
    fireEvent.click(screen.getByRole("button", { name: /Columns/ }));
    const amountCheckbox = screen.getByLabelText(/Amount/) as HTMLInputElement;
    fireEvent.click(amountCheckbox);

    // Amount column should be removed
    expect(screen.queryByText("$100.00")).toBeNull();

    // Preference persisted
    const stored = localStorage.getItem(`ifx-table-prefs:${tableId}`);
    expect(stored).toBeTruthy();
    const parsed = JSON.parse(stored!);
    expect(parsed.visible).not.toContain("amount");

    unmount();
  });

  it("shows empty message when data is empty", () => {
    render(
      <ConfigurableDataTable
        tableId="test-empty"
        columns={COLUMNS}
        data={[]}
        exportable={false}
        searchable={false}
        emptyMessage="Nothing here"
      />,
    );
    expect(screen.getByText("Nothing here")).toBeDefined();
  });
});
