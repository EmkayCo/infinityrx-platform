import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { ProvenanceBreadcrumb } from "../../src/components/ProvenanceBreadcrumb.js";

afterEach(() => cleanup());

describe("ProvenanceBreadcrumb", () => {
  it("renders an empty nav for empty chain", () => {
    render(<ProvenanceBreadcrumb chain={[]} />);
    const nav = screen.getByTestId("provenance-breadcrumb");
    expect(nav.querySelector("a")).toBeNull();
  });

  it("renders all links when chain length ≤ 4", () => {
    render(
      <ProvenanceBreadcrumb
        chain={[
          { label: "Upload 1", href: "/u/1" },
          { label: "Cycle A", href: "/c/a" },
          { label: "Batch 7", href: "/b/7" },
        ]}
      />,
    );
    expect(screen.getAllByRole("link")).toHaveLength(3);
    expect(screen.queryByTestId("provenance-truncated")).toBeNull();
  });

  it("renders 4 links unchanged at exactly the threshold", () => {
    render(
      <ProvenanceBreadcrumb
        chain={[
          { label: "L1", href: "/1" },
          { label: "L2", href: "/2" },
          { label: "L3", href: "/3" },
          { label: "L4", href: "/4" },
        ]}
      />,
    );
    expect(screen.getAllByRole("link")).toHaveLength(4);
    expect(screen.queryByTestId("provenance-truncated")).toBeNull();
  });

  it("truncates middle when chain length > 4 (shows first + … + last 2)", () => {
    render(
      <ProvenanceBreadcrumb
        chain={[
          { label: "L1", href: "/1" },
          { label: "L2", href: "/2" },
          { label: "L3", href: "/3" },
          { label: "L4", href: "/4" },
          { label: "L5", href: "/5" },
        ]}
      />,
    );
    const links = screen.getAllByRole("link");
    expect(links).toHaveLength(3);
    expect(links[0]?.textContent).toBe("L1");
    expect(links[1]?.textContent).toBe("L4");
    expect(links[2]?.textContent).toBe("L5");
    expect(screen.getByTestId("provenance-truncated")).toBeTruthy();
  });

  it("uses aria-label='Provenance' on the nav", () => {
    render(<ProvenanceBreadcrumb chain={[{ label: "x", href: "/x" }]} />);
    expect(screen.getByRole("navigation").getAttribute("aria-label")).toBe("Provenance");
  });
});
