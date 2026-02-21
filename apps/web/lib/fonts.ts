import { Inter, Instrument_Serif, Geist_Mono } from "next/font/google"

export const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
})

export const instrumentSerif = Instrument_Serif({
  variable: "--font-instrument-serif",
  weight: "400",
  subsets: ["latin"],
  display: "swap",
})

export const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  display: "swap",
})

export const fontVariables = `${inter.variable} ${instrumentSerif.variable} ${geistMono.variable}`
