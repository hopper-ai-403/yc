import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import type { ReactNode } from "react";

import { AppShell } from "@/components/layout";
import { ErrorBoundary } from "@/components/error-boundary";
import { AppProviders } from "@/providers";
import { APP_NAME } from "@/lib/constants";

import "@/styles/globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

function resolveMetadataBase(): URL {
  if (process.env.NEXT_PUBLIC_APP_URL) {
    return new URL(process.env.NEXT_PUBLIC_APP_URL);
  }
  if (process.env.VERCEL_URL) {
    return new URL(`https://${process.env.VERCEL_URL}`);
  }
  return new URL("http://localhost:3100");
}

export const metadata: Metadata = {
  title: {
    default: APP_NAME,
    template: `%s · ${APP_NAME}`,
  },
  description:
    "Batch audio intelligence: emotion, acoustic, and technical analysis of customer call recordings.",
  applicationName: APP_NAME,
  keywords: [
    "audio intelligence",
    "call analytics",
    "speech emotion",
    "noise detection",
    "SaaS",
  ],
  authors: [{ name: "Audio Intelligence Studio" }],
  creator: "Audio Intelligence Studio",
  metadataBase: resolveMetadataBase(),
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#0B0B12" },
    { media: "(prefers-color-scheme: light)", color: "#0B0B12" },
  ],
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className="dark">
      <body className={`${inter.variable} ${jetbrainsMono.variable} font-sans`}>
        <AppProviders>
          <ErrorBoundary>
            <AppShell>{children}</AppShell>
          </ErrorBoundary>
        </AppProviders>
      </body>
    </html>
  );
}
