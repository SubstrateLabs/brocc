import "./globals.css";
import { AuthKitProvider } from "@workos-inc/authkit-nextjs/components";
import { getSignInUrl, withAuth } from "@workos-inc/authkit-nextjs";
import type { Metadata } from "next";
import { IBM_Plex_Sans } from "next/font/google";
import { Analytics } from "@vercel/analytics/react";
import { ThemeProvider } from "@/components/theme-provider";
import { SWRConfig } from "swr";
import { Header } from "../components/header";
import { Footer } from "../components/footer";

const ibmPlexSans = IBM_Plex_Sans({
  variable: "--font-ibm-plex-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

// Berkeley Mono Variable is loaded via @font-face in globals.css

export const metadata: Metadata = {
  title: "Brocc | Know thyself",
  description: "Search your life",
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
  const { user } = await withAuth();
  const signInUrl = await getSignInUrl();

  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="preload" href="/BerkeleyMonoVariable.woff2" as="font" type="font/woff2" crossOrigin="anonymous" />
      </head>
      <body className={`${ibmPlexSans.variable} antialiased`}>
        <ThemeProvider attribute="class" defaultTheme="light" enableSystem={false}>
          <AuthKitProvider>
            <SWRConfig
              value={{
                refreshInterval: 5000,
                revalidateOnFocus: true,
              }}
            >
              <div className="min-h-screen flex flex-col">
                <Header user={user ? { ...user, id: user.id } : null} signInUrl={signInUrl} />
                <div className="flex-1">
                  {children}
                </div>
                <Footer />
              </div>
            </SWRConfig>
          </AuthKitProvider>
        </ThemeProvider>
        <Analytics />
      </body>
    </html>
  );
}
