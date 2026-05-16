import { describe, it, expect, vi } from "vitest";
import { render, cleanup } from "@testing-library/react";

vi.mock("server-only", () => ({}));
vi.mock("@infinityrx/qa-harness", () => ({
  ServicesHealth: () => <div data-testid="services-health" />,
  CompositionViewer: ({ manifest }: { manifest: unknown }) => (
    <div data-testid="composition-viewer">{JSON.stringify(manifest)}</div>
  ),
  MockToggle: () => <div data-testid="mock-toggle" />,
  FactoryBindings: () => <div data-testid="factory-bindings" />,
  CorrelationIdJump: () => <div data-testid="correlation-jump" />,
}));
// Note: _generated/manifest.json is aliased to src/__mocks__/manifest.json in
// vitest.config.ts so no vi.mock() is needed here. The alias intercepts at the
// module resolution layer (bypassing import-attribute caching quirks).

import { QaHarnessPage } from "../routes/qa-harness/page.js";
import { CompositionPage } from "../routes/qa-harness/composition/page.js";
import { MockTogglePage } from "../routes/qa-harness/mock-toggle/page.js";
import { FactoryPage } from "../routes/qa-harness/factory/page.js";
import { CorrelationPage } from "../routes/qa-harness/correlation/page.js";

describe("qa-harness pages", () => {
  it("/qa-harness renders ServicesHealth", async () => {
    const { getByTestId } = render(
      await QaHarnessPage({ clients: [] }) as never
    );
    expect(getByTestId("services-health")).toBeTruthy();
  });

  it("/qa-harness/composition renders CompositionViewer with manifest", () => {
    const { getByTestId } = render(CompositionPage() as never);
    // CompositionViewer is rendered and received the manifest object (any shape —
    // the static import resolves to _generated/manifest.json which is a
    // placeholder at dev time; Plan D overwrites it at build time with real content).
    const viewer = getByTestId("composition-viewer");
    expect(viewer).toBeTruthy();
    // Verify the manifest prop is a valid JSON object (not undefined/null).
    expect(viewer.textContent).not.toBe("");
    expect(viewer.textContent).toContain("instance_name");
  });

  it("/qa-harness/mock-toggle renders MockToggle", () => {
    const { getByTestId } = render(
      MockTogglePage({ clients: [], onToggle: vi.fn() }) as never
    );
    expect(getByTestId("mock-toggle")).toBeTruthy();
  });

  it("/qa-harness/factory renders FactoryBindings", () => {
    const { getByTestId } = render(
      FactoryPage({ bindings: [], onSeed: vi.fn() }) as never
    );
    expect(getByTestId("factory-bindings")).toBeTruthy();
  });

  it("/qa-harness/correlation renders CorrelationIdJump", () => {
    const { getByTestId } = render(CorrelationPage() as never);
    expect(getByTestId("correlation-jump")).toBeTruthy();
  });

  it("each qa-harness page has an <h1> heading", () => {
    const pages = [
      CompositionPage(),
      MockTogglePage({ clients: [], onToggle: vi.fn() }),
      FactoryPage({ bindings: [], onSeed: vi.fn() }),
      CorrelationPage(),
    ];
    for (const page of pages) {
      const { getByRole } = render(page as never);
      expect(getByRole("heading", { level: 1 })).toBeTruthy();
      cleanup();
    }
  });
});
