import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { HashChainBadge } from "../../src/components/HashChainBadge.js";

afterEach(() => cleanup());

describe("HashChainBadge", () => {
  it("renders verified state when verified=true", () => {
    render(<HashChainBadge verified={true} />);
    expect(screen.getByTestId("hash-chain-verified").textContent).toContain("Verified");
  });

  it("renders failed state when verified=false", () => {
    render(<HashChainBadge verified={false} />);
    expect(screen.getByTestId("hash-chain-failed").textContent).toContain("Failed");
  });

  it("renders deferred state when verified=null and tooLarge=true", () => {
    render(<HashChainBadge verified={null} tooLarge={true} />);
    expect(screen.getByTestId("hash-chain-too-large").textContent).toContain("Deferred");
  });

  it("renders loading state when verified=null and tooLarge=false/default", () => {
    render(<HashChainBadge verified={null} />);
    expect(screen.getByTestId("hash-chain-loading")).toBeTruthy();
  });
});
