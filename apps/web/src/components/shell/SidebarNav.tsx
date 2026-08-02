"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { isActiveRoute, NAV_ITEMS } from "@/lib/navigation";

/**
 * Primary section navigation for the authenticated shell.
 *
 * A Client Component for one reason: marking the active route requires the
 * current pathname, which only the browser knows. It is deliberately the
 * smallest possible client boundary — the surrounding layout, header and page
 * content all stay on the server, so the bundle cost is this list and nothing
 * else.
 *
 * Styling is semantic tokens only ([[Design System]] §3a). No `dark:` variant
 * appears here: dark mode is a remapping of the token layer, and a
 * theme-aware component would leak that decision back out of it (§6.4).
 */
export function SidebarNav() {
  const pathname = usePathname();

  return (
    <nav aria-label="Main" className="flex flex-col gap-1">
      {NAV_ITEMS.map((item) => {
        const active = isActiveRoute(item.href, pathname);

        return (
          <Link
            key={item.href}
            href={item.href}
            /*
             * aria-current is what conveys "you are here" to a screen reader.
             * Color alone would not — it is invisible to assistive technology
             * and to anyone who cannot distinguish the two states.
             */
            aria-current={active ? "page" : undefined}
            className={[
              "rounded-md px-3 py-2 text-sm transition-colors",
              active
                ? "bg-surface-raised font-medium text-accent"
                : "text-text-muted hover:bg-surface-raised hover:text-text",
            ].join(" ")}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
