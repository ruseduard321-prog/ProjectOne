"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { isActiveRoute, NAV_ITEMS } from "@/lib/navigation";

/**
 * The navigation destinations, rendered on the navigation plane.
 *
 * A Client Component for one reason: marking the active route requires the
 * current pathname, which only the browser knows. Shared by the persistent
 * rail ({@link SidebarNav}) and the mobile drawer ({@link MobileNav}) so the
 * two cannot disagree about what the navigation contains — a second hardcoded
 * copy in JSX is how an item gets renamed in one place and not the other.
 *
 * ## The navigation plane
 *
 * Styling references the `nav-*` family exclusively. That family has existed,
 * been contrast-verified in CI and been referenced by nothing since STEP-26;
 * this is its first consumer. [[ADR-003 Product Visual Language and Token
 * Semantics]] Decision 3 states the rule it satisfies: *a component rendering
 * inside the navigation plane references the `nav-*` family, and a component
 * rendering on the canvas never does.*
 *
 * The plane is dark in **both** themes, which is why `--color-accent-on-nav`
 * is one step lighter than the canvas accent and identical across themes: the
 * light-mode canvas accent measures 3.99 here and fails AA outright.
 *
 * No `dark:` variant appears here. Dark mode is a remapping of the token
 * layer, and a theme-aware component leaks that decision back out of it (§6.4).
 */
export interface NavLinksProps {
  /**
   * Called after a destination is chosen.
   *
   * The drawer uses it to close itself. The rail passes nothing: a persistent
   * rail has no dismissal, and inventing one would be state with no purpose.
   */
  readonly onNavigate?: () => void;
}

export function NavLinks({ onNavigate }: NavLinksProps) {
  const pathname = usePathname();

  return (
    <ul className="flex flex-col gap-1">
      {NAV_ITEMS.map((item) => {
        const active = isActiveRoute(item.href, pathname);

        return (
          <li key={item.href}>
            <Link
              href={item.href}
              onClick={onNavigate}
              /*
               * aria-current is what conveys "you are here" to a screen reader.
               * Colour alone would not — it is invisible to assistive
               * technology and to anyone who cannot distinguish the two states
               * (§9.1 rule 3, WCAG 1.4.1).
               */
              aria-current={active ? "page" : undefined}
              className={[
                // min-h-11 is the 44px coarse-pointer target §9.1 rule 9
                // requires. The rail is where a thumb lands first on a phone.
                "flex min-h-11 items-center rounded-md px-3 py-2 text-sm",
                "transition-colors duration-(--duration-fast) ease-(--ease-standard)",
                active
                  ? "bg-nav-surface-raised font-medium text-accent-on-nav"
                  : "text-text-on-nav-muted hover:bg-nav-surface-raised hover:text-text-on-nav",
              ].join(" ")}
            >
              {item.label}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
