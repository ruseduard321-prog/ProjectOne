import { NavLinks } from "@/components/shell/NavLinks";

/**
 * The persistent navigation rail.
 *
 * A Server Component: it contributes the `<nav>` landmark and its accessible
 * name, and delegates the destinations to {@link NavLinks}, which is the only
 * part that needs the pathname. Keeping the boundary there rather than here is
 * what stops the rail's chrome from shipping as client JavaScript.
 *
 * **Persistent from `md`, a drawer below it** ([[Design System]] §9a rule 2).
 * The hiding is done by the shell layout that places this, not here: a
 * component that decides its own visibility is a component that cannot be
 * placed anywhere else.
 *
 * Exactly one navigation landmark is ever exposed. This one and the drawer's
 * carry the same name deliberately — they are the same navigation — and the
 * viewport guarantees that whichever is not in use is `display: none`, and so
 * absent from the accessibility tree rather than a duplicate landmark in it.
 */
export function SidebarNav() {
  return (
    <nav aria-label="Main">
      <NavLinks />
    </nav>
  );
}
