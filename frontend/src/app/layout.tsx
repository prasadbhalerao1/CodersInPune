import { AuthKitProvider } from "@workos-inc/authkit-nextjs/components";
import type { Metadata } from "next";
import { Bebas_Neue, Geist, Geist_Mono, Instrument_Serif, Syne } from "next/font/google";

import { SITE_DESCRIPTION, SITE_URL } from "@/lib/site";

import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

// Brand display face: headlines and moments that matter, never body text.
const display = Instrument_Serif({
  variable: "--font-instrument-serif",
  subsets: ["latin"],
  weight: "400",
  style: ["normal", "italic"],
});

const syne = Syne({
  variable: "--font-syne",
  subsets: ["latin"],
  weight: ["700", "800"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

// Landing-page display faces (script lead-in and condensed headline). Self-hosted via
// next/font so they neither block rendering nor shift layout.

const bebasNeue = Bebas_Neue({
  variable: "--font-bebas-neue",
  subsets: ["latin"],
  weight: "400",
});

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: "Relay: organisational continuity", template: "%s · Relay" },
  description: SITE_DESCRIPTION,
  applicationName: "Relay",
  keywords: [
    "organisational continuity",
    "handover",
    "ownership",
    "knowledge transfer",
    "bus factor",
    "offboarding",
  ],
  alternates: { canonical: "/", types: { "text/plain": "/llms.txt" } },
  openGraph: {
    type: "website",
    siteName: "Relay",
    title: "Relay: keep work moving when people move on",
    description: SITE_DESCRIPTION,
    url: "/",
  },
  twitter: { card: "summary", title: "Relay", description: SITE_DESCRIPTION },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} ${display.variable} ${syne.variable} ${bebasNeue.variable} dark h-full antialiased`}
    >
      <body className="h-full bg-[#06070B] text-[#F5F5F7]">
        <AuthKitProvider>{children}</AuthKitProvider>
      </body>
    </html>
  );
}
