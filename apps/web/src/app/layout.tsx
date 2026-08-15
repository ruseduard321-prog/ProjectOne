import type { Metadata } from "next";
import { Inter, Instrument_Serif } from "next/font/google";
import "./globals.css";

/**
 * Inter, self-hosted at build time by next/font — never a CDN link, which is
 * a render-blocking dependency on a third party and leaks every visitor's IP
 * to them ([[Design System]] §5.1).
 *
 * Exposed as a CSS variable rather than a class so the token layer owns the
 * font stack: globals.css maps --font-inter into --font-sans alongside the
 * fallbacks, and components only ever see the semantic name.
 */
const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

/**
 * The editorial display face, self-hosted on the same terms as Inter.
 *
 * One weight, deliberately. It is used only at --text-2xl and above — page
 * titles and the few large headings where the approved direction's editorial
 * quality actually lives — so additional weights would be payload nothing
 * renders ([[Design System]] §5.1a, ADR-003 §5).
 */
const instrumentSerif = Instrument_Serif({
  subsets: ["latin"],
  weight: "400",
  display: "swap",
  variable: "--font-instrument-serif",
});

export const metadata: Metadata = {
  title: "ProjectOne",
  description: "An AI Operating System for content businesses.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} ${instrumentSerif.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
