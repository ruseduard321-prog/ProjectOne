import { PageTemplate } from "@/components/shell/PageTemplate";

/**
 * Assigns this route its page template (ADR-007 Decision 8).
 *
 * **Cockpit** — full-bleed, height-aware, one primary action region. The
 * dashboard operates the workspace rather than editing one thing in it, and it
 * is the one surface whose value comes from seeing everything at once, so it is
 * the one surface that is not capped to a reading measure.
 *
 * A segment layout rather than a wrapper inside the page, so `page.tsx`,
 * `loading.tsx` and `error.tsx` all render inside the same template. The
 * attribute is therefore present in the first byte of HTML for every state
 * this route can be in, and never changes while the user is on it.
 */
export default function DashboardLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return <PageTemplate template="cockpit">{children}</PageTemplate>;
}
