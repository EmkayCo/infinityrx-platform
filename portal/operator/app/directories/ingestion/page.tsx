// SP-2 Plan C: page wrapper.
// Logic in @infinityrx/module-directories — IngestionConsolePage.
//
// Client component so we can read the NextAuth session token and inject it
// as an Authorization header into all BFF fetches. Without this, the BFF's
// _verifyAuth() returns 401 and the table never loads.
//
// authReady gates the React Query fetch so it doesn't fire before the session
// resolves (which would result in a 401 before the token is available).
"use client";

import { useSession } from "next-auth/react";
import { useMemo } from "react";
import { IngestionConsolePage } from "@infinityrx/module-directories";

export default function Page() {
  const { data: session, status } = useSession();
  const token = (session as unknown as { access_token?: string } | null)
    ?.access_token;

  // authReady: true once NextAuth has resolved the session (authenticated or not).
  // This gates the React Query fetch so it doesn't fire unauthenticated.
  const authReady = status !== "loading";

  // Build a fetch wrapper that attaches the Bearer token on every request.
  // Re-memoised only when the token changes so the reference stays stable.
  const fetchFn: typeof fetch = useMemo(() => {
    if (!token) return fetch;
    return (input, init) =>
      fetch(input, {
        ...init,
        headers: {
          ...(init?.headers as Record<string, string> | undefined),
          Authorization: `Bearer ${token}`,
        },
      });
  }, [token]);

  return <IngestionConsolePage fetchFn={fetchFn} authReady={authReady} />;
}
