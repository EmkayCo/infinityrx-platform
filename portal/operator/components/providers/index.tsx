"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SessionProvider } from "next-auth/react";
import { Toaster } from "sonner";
import { useState } from "react";
import type { Session } from "next-auth";

interface ProvidersProps {
  children: React.ReactNode;
  session?: Session | null;
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
