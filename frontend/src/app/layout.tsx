import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import { AppProviders } from "@/components/providers";

export const metadata: Metadata = {
  metadataBase: new URL("https://paypool-ai.vercel.app"),
  applicationName: "PayPool",
  title: {
    default: "PayPool | Shared buying power for independent shops",
    template: "%s | PayPool",
  },
  description:
    "PayPool helps independent shops buy together, unlock wholesale prices, and share delivery costs with AI-assisted purchasing and control over every order.",
  keywords: [
    "PayPool",
    "group buying",
    "wholesale",
    "independent shops",
    "shared delivery",
    "AI procurement",
  ],
  category: "business",
  openGraph: {
    type: "website",
    locale: "en_US",
    siteName: "PayPool",
    url: "https://paypool-ai.vercel.app",
    title: "PayPool | Independent shops. Shared buying power.",
    description:
      "Buy together, unlock wholesale prices, and share delivery costs while staying in control of every order.",
  },
  twitter: {
    card: "summary_large_image",
    title: "PayPool | Independent shops. Shared buying power.",
    description:
      "Buy together, unlock wholesale prices, and share delivery costs.",
  },
};

export default function RootLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  );
}
