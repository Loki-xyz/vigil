import type { Metadata } from "next"
import { Inter, Instrument_Serif, Geist_Mono } from "next/font/google"
import "./globals.css"
import { ThemeProvider } from "@/components/layout/theme-provider"
import { Sidebar } from "@/components/layout/sidebar"
import { CommandPalette } from "@/components/layout/command-palette"
import { RealtimeListener } from "@/components/layout/realtime-listener"
import { Providers } from "@/components/providers"
import { Toaster } from "@/components/ui/sonner"

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
})

const instrumentSerif = Instrument_Serif({
  variable: "--font-instrument-serif",
  weight: "400",
  subsets: ["latin"],
})

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
})

const appName = process.env.NEXT_PUBLIC_APP_NAME || "Vigil"

export const metadata: Metadata = {
  title: `${appName} — Judgment Intelligence Monitor`,
  description:
    "Real-time monitoring of Supreme Court and High Court judgments by entity, topic, or statutory reference.",
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${inter.variable} ${instrumentSerif.variable} ${geistMono.variable} font-sans antialiased`}
      >
        <ThemeProvider>
          <Providers>
            <div className="flex h-screen overflow-hidden">
              <Sidebar />
              <main className="flex-1 overflow-y-auto p-6">{children}</main>
            </div>
            <CommandPalette />
            <RealtimeListener />
            <Toaster />
          </Providers>
        </ThemeProvider>
      </body>
    </html>
  )
}
