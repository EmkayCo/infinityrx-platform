import type { Metadata } from "next";
import { headers } from "next/headers";
import { Inter, JetBrains_Mono } from "next/font/google";
import { Providers } from "@/components/providers";
import { AppShell } from "@/components/layout/app-shell";
import { themeInitScript } from "@shared/components/theme-toggle";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
  axes: ["opsz"],
  style: ["normal", "italic"],
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains-mono",
  display: "swap",
  style: ["normal", "italic"],
});

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
  // Middleware (proxy.ts) already verified the JWT and set this header.
  // Reading it here is free — no second JWT parse on the critical render path.
  const h = await headers();
  const isAuthenticated = h.get("x-ifx-authenticated") === "1";

  return (
    <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable}`} suppressHydrationWarning>
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

        {/* SessionProvider with no initial session lazy-fetches /api/auth/session
            on mount — only if a component actually calls useSession()/useAuth(). */}
        <Providers>
          <AppShell isAuthenticated={isAuthenticated}>
            {children}
          </AppShell>
        </Providers>
      </body>
    </html>
  );
}
