import type { Metadata } from "next"
import { fontVariables } from "@/lib/fonts"
import "../globals.css"
import { ThemeProvider } from "@/components/layout/theme-provider"

export const metadata: Metadata = {
  title: "Vigil — Login",
}

export default function LoginLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${fontVariables} font-sans antialiased`}
      >
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  )
}
