// tests/unit/surfaces/exclusions.test.tsx
// Task B-6: Exclusions cluster — ExclusionsPage render tests.
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import React from "react";

import { ExclusionsPage } from "../../../src/surfaces/exclusions/ExclusionsPage.js";

function wrap(ui: React.ReactElement) {
  return render(ui);
}

describe("ExclusionsPage", () => {
  afterEach(() => { cleanup(); });

  it("renders page root and title", () => {
    wrap(<ExclusionsPage />);
    expect(screen.getByTestId("exclusions-page")).toBeTruthy();
    expect(screen.getByTestId("exclusions-title").textContent).toBe("Exclusions Reference");
  });

  it("renders tab bar with all 5 tabs", () => {
    wrap(<ExclusionsPage />);
    expect(screen.getByTestId("tab-cms_opt_out")).toBeTruthy();
    expect(screen.getByTestId("tab-ofac_sdn")).toBeTruthy();
    expect(screen.getByTestId("tab-sam_exclusions")).toBeTruthy();
    expect(screen.getByTestId("tab-oig_leie")).toBeTruthy();
    expect(screen.getByTestId("tab-dea_registrations")).toBeTruthy();
  });

  it("defaults to CMS Opt-Out tab", () => {
    wrap(<ExclusionsPage />);
    expect(screen.getByTestId("tab-cms_opt_out").getAttribute("aria-selected")).toBe("true");
    expect(screen.getByTestId("cms_opt_out-tab")).toBeTruthy();
  });

  it("renders FreshnessChip for cms_opt_out source", () => {
    wrap(<ExclusionsPage cms_opt_out_last_run_at="2024-04-01" />);
    const chip = document.querySelector(".freshness-chip");
    expect(chip).toBeTruthy();
    expect(chip?.textContent).toContain("cms_opt_out");
  });

  it("renders FreshnessChip in red when no cms_opt_out run date", () => {
    wrap(<ExclusionsPage cms_opt_out_last_run_at={null} />);
    expect(document.querySelector(".freshness-chip")?.className).toContain("red");
  });

  it("renders CMS Opt-Out card with title and description", () => {
    wrap(<ExclusionsPage />);
    expect(screen.getByTestId("cms_opt_out-card")).toBeTruthy();
    expect(screen.getByTestId("cms_opt_out-title").textContent).toBe("CMS Opt-Out");
    expect(screen.getByTestId("cms_opt_out-description").textContent).toContain("Medicare");
  });

  it("renders cms_opt_out no-route note", () => {
    wrap(<ExclusionsPage />);
    expect(screen.getByTestId("cms_opt_out-no-route-note")).toBeTruthy();
    expect(screen.getByTestId("cms_opt_out-no-route-note").textContent).toContain(
      "Live search is not yet available"
    );
  });

  it("switches to OFAC SDN tab and shows OFAC content", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    wrap(<ExclusionsPage />);
    await userEvent.click(screen.getByTestId("tab-ofac_sdn"));
    expect(screen.getByTestId("tab-ofac_sdn").getAttribute("aria-selected")).toBe("true");
    expect(screen.getByTestId("ofac_sdn-tab")).toBeTruthy();
    expect(screen.getByTestId("ofac_sdn-title").textContent).toBe("OFAC SDN");
    expect(screen.getByTestId("ofac_sdn-description").textContent).toContain(
      "Specially Designated Nationals"
    );
  });

  it("renders FreshnessChip for ofac_sdn source when run date provided", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    wrap(<ExclusionsPage ofac_sdn_last_run_at="2024-04-15" />);
    await userEvent.click(screen.getByTestId("tab-ofac_sdn"));
    const chip = document.querySelector(".freshness-chip");
    expect(chip?.textContent).toContain("ofac_sdn");
  });

  it("switches to SAM Exclusions tab", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    wrap(<ExclusionsPage />);
    await userEvent.click(screen.getByTestId("tab-sam_exclusions"));
    expect(screen.getByTestId("sam_exclusions-tab")).toBeTruthy();
    expect(screen.getByTestId("sam_exclusions-title").textContent).toBe("SAM Exclusions");
    expect(screen.getByTestId("sam_exclusions-description").textContent).toContain("SAM.gov");
  });

  it("switches to OIG LEIE tab", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    wrap(<ExclusionsPage />);
    await userEvent.click(screen.getByTestId("tab-oig_leie"));
    expect(screen.getByTestId("oig_leie-tab")).toBeTruthy();
    expect(screen.getByTestId("oig_leie-title").textContent).toBe("OIG LEIE");
    expect(screen.getByTestId("oig_leie-description").textContent).toContain("OIG");
  });

  it("switches to DEA Registrations tab", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    wrap(<ExclusionsPage />);
    await userEvent.click(screen.getByTestId("tab-dea_registrations"));
    expect(screen.getByTestId("dea_registrations-tab")).toBeTruthy();
    expect(screen.getByTestId("dea_registrations-title").textContent).toBe("DEA Registrations");
    expect(screen.getByTestId("dea_registrations-description").textContent).toContain("DEA");
  });

  it("renders FreshnessChip in red when dea_registrations run date missing", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    wrap(<ExclusionsPage dea_registrations_last_run_at={null} />);
    await userEvent.click(screen.getByTestId("tab-dea_registrations"));
    expect(document.querySelector(".freshness-chip")?.className).toContain("red");
  });

  it("hides non-active tab content", () => {
    wrap(<ExclusionsPage />);
    // CMS Opt-Out is active; others should not be rendered
    expect(screen.queryByTestId("ofac_sdn-tab")).toBeNull();
    expect(screen.queryByTestId("sam_exclusions-tab")).toBeNull();
    expect(screen.queryByTestId("oig_leie-tab")).toBeNull();
    expect(screen.queryByTestId("dea_registrations-tab")).toBeNull();
  });

  it("tab aria-selected updates when switching tabs", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    wrap(<ExclusionsPage />);
    await userEvent.click(screen.getByTestId("tab-oig_leie"));
    expect(screen.getByTestId("tab-oig_leie").getAttribute("aria-selected")).toBe("true");
    expect(screen.getByTestId("tab-cms_opt_out").getAttribute("aria-selected")).toBe("false");
  });
});
