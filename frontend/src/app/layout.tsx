import { AuthKitProvider } from "@workos-inc/authkit-nextjs/components";
import type { Metadata } from "next";
import { Geist, Geist_Mono, Instrument_Serif } from "next/font/google";

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
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
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
      className={`${geistSans.variable} ${geistMono.variable} ${display.variable} h-full antialiased`}
    >
      <body className="h-full">
        <AuthKitProvider>{children}</AuthKitProvider>
      </body>
    </html>
  );
}
