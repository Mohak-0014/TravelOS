import type { Metadata } from "next";
import { Fraunces, Instrument_Sans, Spline_Sans_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

// Editorial display serif for headlines — trimmed to the weights actually used
const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-fraunces",
  weight: ["400", "500", "600"],
  style: ["normal", "italic"],
  display: "swap",
});

// Quiet, precise grotesk for UI / body
const instrument = Instrument_Sans({
  subsets: ["latin"],
  variable: "--font-instrument",
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

// True mono for data: prices, dates, IATA codes, coordinates
const splineMono = Spline_Sans_Mono({
  subsets: ["latin"],
  variable: "--font-spline-mono",
  weight: ["400", "500", "600"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "TravelOS — Your AI Travel Companion",
  description: "The travel planning system that remembers you and gets smarter every trip.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${fraunces.variable} ${instrument.variable} ${splineMono.variable} antialiased bg-paper text-ink-900`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
