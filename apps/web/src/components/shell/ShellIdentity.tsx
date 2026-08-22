import Link from "next/link";

/**
 * The product's own identity, at the head of the navigation plane.
 *
 * ## Why this is ProjectOne and not the workspace
 *
 * [[Design System]] §7.2 describes workspace identity at the top of the rail,
 * and the rail cannot render it truthfully today. The workspace is resolved
 * **per page** (`lib/workspace.ts`, from `GET /workspaces`), not in the shell
 * layout, which holds only the signed-in profile. Putting a workspace name
 * here would mean either inventing one — forbidden outright
 * ([[CLAUDE|CLAUDE.md]] §35) — or adding an API request to the shell purely to
 * decorate it, which [[STEP-31a Product Experience Blueprint Alignment]]
 * excludes.
 *
 * So the plane states what the shell actually knows: the product. §7.2 is
 * corrected to describe that rather than the other way round — documentation
 * describing behaviour the code does not have is worse than none, because it
 * actively misleads ([[CLAUDE|CLAUDE.md]] §19).
 *
 * A Server Component. Sans, not the display face: the wordmark sits well below
 * `--text-2xl`, which is the boundary ADR-003 Decision 5 draws for the serif.
 */
export interface ShellIdentityProps {
  /**
   * Whether the wordmark links to the dashboard.
   *
   * The rail links. The drawer does not: the mobile header already carries the
   * same destination one element away, and a second copy would add a tab stop
   * that goes where the user can already go.
   */
  readonly asLink?: boolean;
}

export function ShellIdentity({ asLink = false }: ShellIdentityProps) {
  const label = "ProjectOne";
  const className = "text-base font-semibold tracking-tight text-text-on-nav";

  if (!asLink) {
    return <span className={className}>{label}</span>;
  }

  return (
    <Link href="/dashboard" className={`${className} rounded-md`}>
      {label}
    </Link>
  );
}
