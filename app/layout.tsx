import type { Metadata, Viewport } from "next";
import { headers } from "next/headers";
import { AppProviders } from "@/components/providers/app-providers";
import { ServiceWorkerRegistration } from "@/components/pwa/service-worker-registration";
import "./globals.css";

export async function generateMetadata(): Promise<Metadata> {
  const requestHeaders = await headers();
  const host = requestHeaders.get("x-forwarded-host") ?? requestHeaders.get("host") ?? "localhost:5173";
  const protocol = requestHeaders.get("x-forwarded-proto") ?? (host.startsWith("localhost") ? "http" : "https");
  const origin = `${protocol}://${host}`;

  return {
    metadataBase: new URL(origin),
    title: {
      default: "PokéLens — Pokémon card scanner",
      template: "%s · PokéLens",
    },
    description:
      "Identify a Pokémon card from one photo and see the exact printing, confidence, and current market price.",
    applicationName: "PokéLens",
    appleWebApp: {
      capable: true,
      statusBarStyle: "black-translucent",
      title: "PokéLens",
    },
    formatDetection: { telephone: false },
    icons: {
      icon: "/favicon.svg",
      shortcut: "/favicon.svg",
      apple: "/favicon.svg",
    },
    openGraph: {
      type: "website",
      siteName: "PokéLens",
      title: "PokéLens — One photo. The right card.",
      description:
        "A fast, confidence-first Pokémon card scanner with current market pricing.",
      images: [{ url: `${origin}/og.png`, width: 1731, height: 909, alt: "PokéLens card scanner" }],
    },
    twitter: {
      card: "summary_large_image",
      title: "PokéLens — One photo. The right card.",
      description:
        "A fast, confidence-first Pokémon card scanner with current market pricing.",
      images: [`${origin}/og.png`],
    },
  };
}

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  viewportFit: "cover",
  themeColor: "#080b10",
  colorScheme: "dark",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <AppProviders>
          {children}
          <ServiceWorkerRegistration />
        </AppProviders>
      </body>
    </html>
  );
}
