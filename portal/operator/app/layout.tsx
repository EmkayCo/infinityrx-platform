import type { Metadata } from "next";
import { headers } from "next/headers";
import { Lato, IBM_Plex_Mono } from "next/font/google";
import { Providers } from "@/components/providers";
import { AppShell } from "@/components/layout/app-shell";
import { ManifestNav } from "./_nav/manifest-nav";
import { themeInitScript } from "@shared/components/theme-toggle";
import "./globals.css";

const lato = Lato({
  subsets: ["latin"],
  weight: ["300", "400", "700", "900"],
  variable: "--font-lato",
  display: "swap",
});

const ibmPlexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-ibm-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "InfinityRx ICP",
    template: "%s | InfinityRx ICP",
  },
  description: "InfinityRx ICP Operator Portal",
  robots: { index: false, follow: false },
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const h = await headers();
  const isAuthenticated = h.get("x-ifx-authenticated") === "1";

  return (
    <html lang="en" className={`${lato.variable} ${ibmPlexMono.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className="min-h-screen bg-[var(--ifx-bg)] font-sans antialiased">
        <a href="#main-content" className="skip-nav">
          Skip to main content
        </a>

        <Providers>
          <AppShell isAuthenticated={isAuthenticated} nav={<ManifestNav />}>
            {children}
          </AppShell>
        </Providers>
      </body>
    </html>
  );
}
