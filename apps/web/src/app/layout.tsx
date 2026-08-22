import type { Metadata } from "next";
import { Inter, Instrument_Serif } from "next/font/google";

import { THEME_INIT_SCRIPT } from "@/lib/theme";
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
    /*
     * `suppressHydrationWarning` is scoped to this one element and is load-
     * bearing: the script below sets `data-theme` on it before React hydrates,
     * so the server's markup (no attribute) and the client's DOM (attribute)
     * legitimately differ. Without it React logs a mismatch for a difference it
     * is not entitled to have an opinion about. It suppresses nothing about
     * `<body>` or anything inside it.
     */
    <html
      lang="en"
      className={`${inter.variable} ${instrumentSerif.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <head>
        {/*
         * Applies an explicit theme choice BEFORE first paint. An effect would
         * run after it, producing a visible flash of the wrong theme on every
         * load — see `lib/theme.ts` for why this is the only place it can go.
         *
         * `dangerouslySetInnerHTML` is the only way to emit an inline script
         * from JSX. The content is a module constant built from constants in
         * this repository, with no interpolation of anything a request or a
         * user can influence, so there is no injection surface here.
         */}
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>

      {/*
       * `<body>` carries global theme state only, and today carries none of it
       * directly — `data-theme` and `color-scheme` both live on `:root`
       * (ADR-007 Decisions 6 and 7). What matters is what is NOT here: no
       * per-route and no per-template attribute. Templates are emitted by the
       * `PageTemplate` wrapper on its own element, so a route can never leak
       * its layout into the next one.
       */}
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
