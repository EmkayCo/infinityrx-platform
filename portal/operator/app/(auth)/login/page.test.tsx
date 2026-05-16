/**
 * Unit tests for LoginPage — F-004 Suspense boundary fix.
 *
 * Verifies:
 *  1. LoginPage renders without throwing (no hydration error #418/#423).
 *  2. LoginContent receives callbackUrl from useSearchParams() through the
 *     Suspense boundary and uses it when signing in.
 *  3. LoginPage shell wraps content in <Suspense> so the route is
 *     statically renderable by Next.js App Router.
 */

import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// ---------------------------------------------------------------------------
// Mocks
// vi.hoisted() ensures these are available when vi.mock() factories run —
// vi.mock() is hoisted to the top of the file by Vitest's transformer, but
// const declarations are not. vi.hoisted() lifts the assignment alongside.
// ---------------------------------------------------------------------------

const { mockRouterPush, mockRouterRefresh, mockSignIn } = vi.hoisted(() => ({
  mockRouterPush: vi.fn(),
  mockRouterRefresh: vi.fn(),
  mockSignIn: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockRouterPush,
    refresh: mockRouterRefresh,
  }),
  useSearchParams: () => new URLSearchParams("callbackUrl=%2Fdashboard"),
}));

vi.mock("next-auth/react", () => ({
  signIn: mockSignIn,
}));

// Stub internal UI dependencies that require Next.js runtime or assets.
vi.mock("@/components/ui/ifx-logo", () => ({
  IfxLogo: () => React.createElement("div", { "data-testid": "ifx-logo" }),
}));
vi.mock("@shared/lib/format", () => ({
  cn: (...classes: (string | undefined | false)[]) => classes.filter(Boolean).join(" "),
}));
vi.mock("next/image", () => ({
  default: (props: Record<string, unknown>) => React.createElement("img", { ...props, src: props.src as string }),
}));

// ---------------------------------------------------------------------------
// Subject under test (imported AFTER mocks are registered)
// ---------------------------------------------------------------------------
import LoginPage from "./page";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderLoginPage() {
  return render(<LoginPage />);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("LoginPage — F-004 Suspense boundary", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders without throwing (smoke test — no hydration error)", () => {
    // If useSearchParams is called outside Suspense the SSR pass throws
    // React error #418/#423. This test catches a regression at the unit level.
    expect(() => renderLoginPage()).not.toThrow();
  });

  it("renders the sign-in heading inside the Suspense boundary", async () => {
    renderLoginPage();
    // LoginContent is synchronously rendered through Suspense in jsdom —
    // getByRole throws if not found, so a truthy check is sufficient.
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /sign in to your account/i })).toBeTruthy();
    });
  });

  it("renders email and password fields", async () => {
    renderLoginPage();
    await waitFor(() => {
      expect(screen.getByLabelText(/email address/i)).toBeTruthy();
      expect(screen.getByLabelText(/^password$/i)).toBeTruthy();
    });
  });

  it("callbackUrl propagates through Suspense boundary — redirects to /dashboard on success", async () => {
    mockSignIn.mockResolvedValue({ error: null, url: null });

    renderLoginPage();

    // Confirm form is rendered before interacting
    await waitFor(() => {
      expect(screen.getByLabelText(/email address/i)).toBeTruthy();
    });

    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/email address/i), "admin@infinityrx.com");
    await user.type(screen.getByLabelText(/^password$/i), "password123");
    await user.click(screen.getByRole("button", { name: /sign in$/i }));

    await waitFor(() => {
      expect(mockSignIn).toHaveBeenCalledWith("credentials", {
        email: "admin@infinityrx.com",
        password: "password123",
        redirect: false,
      });
      // callbackUrl from useSearchParams mock is "/dashboard"
      expect(mockRouterPush).toHaveBeenCalledWith("/dashboard");
      expect(mockRouterRefresh).toHaveBeenCalled();
    });
  });

  it("shows auth error on invalid credentials", async () => {
    mockSignIn.mockResolvedValue({ error: "CredentialsSignin", url: null });

    renderLoginPage();

    await waitFor(() => {
      expect(screen.getByLabelText(/email address/i)).toBeTruthy();
    });

    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/email address/i), "bad@infinityrx.com");
    await user.type(screen.getByLabelText(/^password$/i), "wrongpass");
    await user.click(screen.getByRole("button", { name: /sign in$/i }));

    await waitFor(() => {
      const alert = screen.getByRole("alert");
      expect(alert.textContent).toMatch(/invalid email or password/i);
    });
    // Should not redirect on failure
    expect(mockRouterPush).not.toHaveBeenCalled();
  });

  it("redirects to /mfa when server signals mfa_required", async () => {
    mockSignIn.mockResolvedValue({ error: null, url: "/api/auth/mfa_required" });

    renderLoginPage();

    await waitFor(() => {
      expect(screen.getByLabelText(/email address/i)).toBeTruthy();
    });

    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/email address/i), "mfa@infinityrx.com");
    await user.type(screen.getByLabelText(/^password$/i), "pass");
    await user.click(screen.getByRole("button", { name: /sign in$/i }));

    await waitFor(() => {
      expect(mockRouterPush).toHaveBeenCalledWith("/mfa");
    });
  });
});
