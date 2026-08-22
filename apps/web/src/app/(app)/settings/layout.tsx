import { PageTemplate } from "@/components/shell/PageTemplate";

/**
 * Assigns this route its page template (ADR-007 Decision 8).
 *
 * **Workbench** — the default working surface. Settings is a stack of
 * independent sections rather than a single task, so it is not Focus; it is
 * work, done at a desk, which is what Workbench is for.
 *
 * A segment layout rather than a wrapper inside the page, so `page.tsx`,
 * `loading.tsx` and `error.tsx` all render inside the same template. The
 * attribute is therefore present in the first byte of HTML for every state
 * this route can be in, and never changes while the user is on it.
 */
export default function SettingsLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return <PageTemplate template="workbench">{children}</PageTemplate>;
}
