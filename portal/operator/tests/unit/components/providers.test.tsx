/**
 * Render test for the Providers shell.
 *
 * The Providers component wires session → api-client. The actual header
 * behavior is covered exhaustively in tests/unit/lib/api-client.test.ts.
 * Here we only verify the component mounts without throwing and renders
 * its children — a smoke test that catches the import/runtime mistakes
 * that would otherwise crash the whole app shell.
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { Providers } from "@/components/providers";

vi.mock("next-auth/react", () => ({
  SessionProvider: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
  useSession: () => ({ data: null, status: "unauthenticated" }),
}));

vi.mock("@shared/lib/api-client", () => ({
  configureApiClient: vi.fn(),
}));

describe("Providers", () => {
  it("renders children inside the provider tree", () => {
    render(
      <Providers>
        <div data-testid="child">hello</div>
      </Providers>
    );
    expect(screen.getByTestId("child")).toHaveTextContent("hello");
  });
});
