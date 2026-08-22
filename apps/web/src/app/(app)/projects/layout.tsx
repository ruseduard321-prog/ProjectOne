import { PageTemplate } from "@/components/shell/PageTemplate";

/**
 * Assigns this route its page template (ADR-007 Decision 8).
 *
 * **Workbench** — the default working surface: wide content, list and detail.
 * Covers `/projects` and `/projects/[projectId]` alike, which is the shape the
 * template names: a list, and one item from it inspected beside its context.
 *
 * A segment layout rather than a wrapper inside the page, so `page.tsx`,
 * `loading.tsx` and `error.tsx` all render inside the same template. The
 * attribute is therefore present in the first byte of HTML for every state
 * this route can be in, and never changes while the user is on it.
 */
export default function ProjectsLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return <PageTemplate template="workbench">{children}</PageTemplate>;
}
