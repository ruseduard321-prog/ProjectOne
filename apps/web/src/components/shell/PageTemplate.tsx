import type { ReactNode } from "react";

/**
 * The page-template contract: every surface uses exactly one of three shapes.
 *
 * ## Why a wrapper and not an attribute on `<body>`
 *
 * The approved blueprint selects a template by mutating `body[data-tpl]` from
 * client-side JavaScript on navigation. That is a prototype technique and
 * [[ADR-007 Product Experience Blueprint Authority and Adoption Boundary]]
 * Decision 8 explicitly does not adopt it, for three reasons:
 *
 *  1. It makes `<body>` carry per-route state. `<body>` is global territory —
 *     the theme, and nothing else — so a route that forgot to reset it would
 *     leak its layout into the next route.
 *  2. A Server Component cannot produce it without a hydration race: the first
 *     byte of HTML would carry no template, and the correct one would arrive
 *     after paint. That is a visible reflow on every navigation.
 *  3. The prototype's own template rules depend on `--protobar-height`, which
 *     is demo chrome with no production existence.
 *
 * **The adopted contract instead.** This is a Server Component. The template is
 * a `prop`, resolved on the server by the route that is already rendering, and
 * emitted on this wrapper's own element. It is therefore present in the first
 * byte of HTML, identical on server and client, and never reassigned after
 * paint. Nothing here reads `usePathname()`, and nothing may.
 *
 * The widths themselves live in `globals.css` under `[data-template]`, not in a
 * class ladder here — see the note there. Adding a fourth template is a change
 * to the contract and needs the ADR that supersedes Decision 8, not a new
 * string in the union below.
 */

/** The three shapes, and no fourth. Short forms are canonical (Decision 8). */
export type PageTemplateName = "cockpit" | "workbench" | "focus";

export interface PageTemplateProps {
  /**
   * Which shape this surface is.
   *
   * - `cockpit` — full-bleed, height-aware, one primary action region.
   * - `workbench` — the default working surface: wide content, list and detail.
   * - `focus` — narrow single column, reduced chrome, one task.
   */
  readonly template: PageTemplateName;
  readonly children: ReactNode;
}

export function PageTemplate({ template, children }: PageTemplateProps) {
  return (
    <div data-template={template} className="mx-auto w-full">
      {children}
    </div>
  );
}
