"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SessionProvider, useSession } from "next-auth/react";
import { Toaster } from "sonner";
import { useEffect, useRef, useState } from "react";
import type { Session } from "next-auth";
import { configureApiClient } from "@shared/lib/api-client";

interface ProvidersProps {
  children: React.ReactNode;
  session?: Session | null;
}

/**
 * Bridges the NextAuth session into the shared api-client so every outbound
 * fetch carries Authorization Bearer + x-tenant-id. Without this bridge the
 * api-client's token/tenant providers stay null and every backend call goes
 * out unauthenticated and unscoped — which presents as "no data, no error"
 * because FastAPI 422s on the missing x-tenant-id before the handler runs
 * and the browser preflight 404s before either header matters.
 *
 * Mount this as a child of SessionProvider so useSession() returns the
 * real session token.
 */
function ApiClientBridge() {
  const { data: session } = useSession();
  // Stash latest values in refs so the configure-once effect resolves the
  // current token/tenant each call without forcing re-wiring on every render.
  const tokenRef = useRef<string | null | undefined>(undefined);
  const tenantRef = useRef<string | null | undefined>(undefined);

  tokenRef.current = (session as unknown as { access_token?: string } | null)
    ?.access_token;
  tenantRef.current = session?.user?.tenant_id ?? null;

  useEffect(() => {
    configureApiClient({
      tokenProvider: async () => tokenRef.current ?? null,
      tenantProvider: async () => tenantRef.current ?? null,
    });
  }, []);

  return null;
}

export function Providers({ children, session }: ProvidersProps) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            retry: 2,
            refetchOnWindowFocus: false,
          },
        },
      })
  );

  return (
    <SessionProvider session={session}>
      <ApiClientBridge />
      <QueryClientProvider client={queryClient}>
        {children}
        <Toaster
          position="bottom-right"
          toastOptions={{
            duration: 5000,
            classNames: {
              toast: "border bg-popover text-popover-foreground shadow-lg",
              success: "border-green-500/20 bg-green-50 dark:bg-green-950/50",
              error: "border-red-500/20 bg-red-50 dark:bg-red-950/50",
              warning: "border-amber-500/20 bg-amber-50 dark:bg-amber-950/50",
            },
          }}
        />
      </QueryClientProvider>
    </SessionProvider>
  );
}
