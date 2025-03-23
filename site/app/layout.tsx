import "./globals.css";
import { AuthKitProvider } from "@workos-inc/authkit-nextjs/components";
import type { Metadata } from "next";
import { IBM_Plex_Sans, IBM_Plex_Mono } from "next/font/google";
import { Analytics } from "@vercel/analytics/react";
import { ThemeProvider } from "@/components/theme-provider";
import { SWRConfig } from "swr";

const ibmPlexSans = IBM_Plex_Sans({
  variable: "--font-ibm-plex-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const ibmPlexMono = IBM_Plex_Mono({
  variable: "--font-ibm-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "brocc.",
  description: "link search",
  icons: {
    icon: [
      {
        url: "/brocc.svg",
        type: "image/svg+xml",
      },
    ],
    shortcut: [
      {
        url: "/brocc.svg",
        type: "image/svg+xml",
      },
    ],
    apple: [
      {
        url: "/brocc.svg",
        type: "image/svg+xml",
      },
    ],
  },
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head />
      <body className={`${ibmPlexSans.variable} ${ibmPlexMono.variable} antialiased`}>
        <ThemeProvider attribute="class" defaultTheme="light" enableSystem={false}>
          <AuthKitProvider>
            <SWRConfig
              value={{
                refreshInterval: 5000,
                revalidateOnFocus: true,
              }}
            >
              <div className="flex-1">{children}</div>
            </SWRConfig>
          </AuthKitProvider>
        </ThemeProvider>
        <Analytics />
      </body>
    </html>
  );
}
