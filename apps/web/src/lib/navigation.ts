/**
 * The authenticated shell's navigation structure.
 *
 * Defined as data rather than markup so the nav has one source of truth: the
 * sidebar renders it, and the active-route logic reads the same list. A second
 * hardcoded copy in JSX is how a nav item gets renamed in one place and not the
 * other.
 *
 * Only sections with a scheduled build step appear here. Analytics, Billing and
 * Video Generation are specified in the Project Bible but have no step in the
 * current [[Build Plan]], and a nav item pointing at a route that does not exist
 * is a dead end rather than a roadmap.
 */

export interface NavItem {
  /** Route segment under the authenticated shell. */
  readonly href: string;
  /** Visible label. Also the accessible name. */
  readonly label: string;
}

export const NAV_ITEMS: readonly NavItem[] = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/projects", label: "Projects" },
  { href: "/chat", label: "AI Chat" },
  { href: "/settings", label: "Settings" },
] as const;

/**
 * Whether {@link href} is the active route for the given pathname.
 *
 * A nested route marks its parent active (`/projects/abc` → `/projects`), which
 * is what a user expects from a section nav. The check is segment-aware rather
 * than a plain `startsWith`, so `/projects-archive` does not light up
 * `/projects`.
 */
export function isActiveRoute(href: string, pathname: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}
