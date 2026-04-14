/**
 * ErrorBoundary component tests.
 *
 * The ErrorBoundary is the last line of defense before a crash reaches the
 * user. We verify:
 *   - It catches errors thrown by children and shows the fallback
 *   - Clicking "Retry now" resets the error state
 *   - A custom fallback prop is rendered when provided
 *   - Nested boundaries isolate crashes to the smallest scope
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { screen, fireEvent } from "@testing-library/react";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { renderWithProviders } from "../../fixtures/test-helpers";

function Boom({ shouldThrow = true }: { shouldThrow?: boolean }) {
  if (shouldThrow) {
    throw new Error("Boom went the component");
  }
  return <div data-testid="boom-healthy">Healthy</div>;
}

function Healthy() {
  return <div data-testid="healthy">All good</div>;
}

describe("ErrorBoundary", () => {
  // React logs caught errors via console.error — silence the noise during tests.
  let consoleErrorSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
  });

  it("renders children when they don't throw", () => {
    renderWithProviders(
      <ErrorBoundary>
        <Healthy />
      </ErrorBoundary>
    );
    expect(screen.getByTestId("healthy")).toBeInTheDocument();
  });

  it("catches errors and renders the default fallback with error message", () => {
    renderWithProviders(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
    expect(screen.getByText(/boom went the component/i)).toBeInTheDocument();
  });

  it("renders a Retry button when in error state", () => {
    renderWithProviders(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>
    );
    const retry = screen.getByRole("button", { name: /retry now/i });
    expect(retry).toBeInTheDocument();
  });

  it("clears the error state when Retry is clicked with a recoverable child", () => {
    // Mount a component whose throw state we can toggle
    let shouldThrow = true;
    function Toggle() {
      if (shouldThrow) throw new Error("still broken");
      return <div data-testid="recovered">recovered</div>;
    }
    const { rerender } = renderWithProviders(
      <ErrorBoundary>
        <Toggle />
      </ErrorBoundary>
    );
    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();

    // Fix the underlying issue and click retry
    shouldThrow = false;
    const retry = screen.getByRole("button", { name: /retry now/i });
    fireEvent.click(retry);
    rerender(
      <ErrorBoundary>
        <Toggle />
      </ErrorBoundary>
    );
    expect(screen.queryByText(/something went wrong/i)).not.toBeInTheDocument();
    expect(screen.getByTestId("recovered")).toBeInTheDocument();
  });

  it("renders a custom fallback when the `fallback` prop is provided", () => {
    renderWithProviders(
      <ErrorBoundary fallback={<div data-testid="custom-fallback">Custom Error UI</div>}>
        <Boom />
      </ErrorBoundary>
    );
    expect(screen.getByTestId("custom-fallback")).toBeInTheDocument();
    // Default fallback not rendered
    expect(screen.queryByText(/retry now/i)).not.toBeInTheDocument();
  });

  it("does not catch errors from siblings outside its boundary", () => {
    renderWithProviders(
      <>
        <ErrorBoundary>
          <Healthy />
        </ErrorBoundary>
        <div data-testid="sibling">outside boundary</div>
      </>
    );
    expect(screen.getByTestId("healthy")).toBeInTheDocument();
    expect(screen.getByTestId("sibling")).toBeInTheDocument();
  });

  it("nested boundaries isolate errors to the inner boundary", () => {
    renderWithProviders(
      <ErrorBoundary fallback={<div data-testid="outer-fallback">outer</div>}>
        <div data-testid="outer-chrome">outer chrome</div>
        <ErrorBoundary fallback={<div data-testid="inner-fallback">inner fell back</div>}>
          <Boom />
        </ErrorBoundary>
      </ErrorBoundary>
    );
    // Outer chrome still renders
    expect(screen.getByTestId("outer-chrome")).toBeInTheDocument();
    // Inner fallback rendered
    expect(screen.getByTestId("inner-fallback")).toBeInTheDocument();
    // Outer fallback NOT rendered (outer boundary is still in non-error state)
    expect(screen.queryByTestId("outer-fallback")).not.toBeInTheDocument();
  });
});
