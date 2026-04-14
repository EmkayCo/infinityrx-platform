import type { Metadata } from "next";
import { auth } from "@shared/lib/auth";
import { Providers } from "@/components/providers";
import { AppShell } from "@/components/layout/app-shell";
import { themeInitScript } from "@shared/components/theme-toggle";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "InfinityRx Operator Portal",
    template: "%s | InfinityRx",
  },
  description: "InfinityRx internal operations portal",
  robots: { index: false, follow: false },
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth();
  const isAuthenticated = !!session?.user;

  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* Prevent theme flash */}
        <script
          dangerouslySetInnerHTML={{ __html: themeInitScript }}
        />
      </head>
      <body className="min-h-screen bg-[var(--ifx-bg)] font-sans antialiased">
        {/* Skip navigation for screen readers */}
        <a href="#main-content" className="skip-nav">
          Skip to main content
        </a>

        <Providers session={session}>
          <AppShell isAuthenticated={isAuthenticated}>
            {children}
          </AppShell>
        </Providers>
      </body>
    </html>
  );
}
