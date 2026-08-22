import Link from "next/link";

import { MobileNav } from "@/components/shell/MobileNav";
import { ShellIdentity } from "@/components/shell/ShellIdentity";
import { SidebarNav } from "@/components/shell/SidebarNav";
import { UserMenu } from "@/components/shell/UserMenu";
import { requireProfile } from "@/lib/auth";

/**
 * The authenticated application shell.
 *
 * A route group (`(app)`) rather than a path segment: it wraps every
 * application screen in this chrome without adding `/app` to any URL. Feature
 * steps add route segments inside it and inherit the shell for free.
 *
 * A Server Component. The only client code beneath it is the navigation —
 * `NavLinks` needs the pathname to mark the active route, and `MobileNav`
 * drives an imperative browser API — so everything else here renders on the
 * server and ships no JavaScript.
 *
 * **This layout is the authentication gate** (STEP-16). `requireProfile` resolves
 * the session on the server and redirects to sign-in when there is none, so an
 * unauthenticated request never receives the shell's markup at all — a
 * client-side redirect would have sent the page first and navigated away after
 * ([[Chapter 05 - NextJS Architecture]] §5.10).
 *
 * Placing it here rather than in each page is what makes it hold for screens
 * that do not exist yet: a feature step adding a route inside this group
 * inherits the gate rather than having to remember it.
 *
 * ## The navigation plane
 *
 * The rail renders on the `nav-*` family — the matte-black plane
 * [[ADR-003 Product Visual Language and Token Semantics]] Decision 3 defined
 * and nothing consumed until now. It is a dark surface inside the light theme,
 * which is why it has its own token family: every canvas pairing assumes
 * foreground and background move together with the theme, and navigation
 * breaks that assumption.
 *
 * **Persistent from `md`, a drawer below it** ([[Design System]] §9a rule 2).
 * The rail is `sticky` so a long page scrolls under a navigation that stays
 * where the user left it.
 *
 * **Destinations do not change here.** `NAV_ITEMS` had four entries before this
 * step and has four after ([[ADR-007 Product Experience Blueprint Authority and
 * Adoption Boundary]] Decision 12): navigation grows when routes do, and a nav
 * item pointing at a route that does not exist is a dead end rather than a
 * roadmap.
 */
export default async function AppLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const profile = await requireProfile();

  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      {/*
       * A skip link is the difference between a keyboard user reaching the
       * content in one keystroke and tabbing through every nav item on every
       * page. Visually hidden until focused — and it must be the FIRST
       * focusable element in the document, which is why it precedes everything.
       */}
      <a
        href="#main-content"
        className="sr-only rounded-md bg-surface-raised px-4 py-2 text-sm font-medium text-accent focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50"
      >
        Skip to content
      </a>

      {/*
       * The navigation plane: one full-height column, from the top of the
       * viewport, holding the product's identity, its destinations, and the
       * signed-in user — in that order, top to bottom.
       *
       * It replaces a full-width canvas header sitting ABOVE a rail that held
       * only four links. That arrangement had the plane starting halfway down
       * the screen and reading as an empty black block, and it put the
       * navigation's own chrome — identity, the signed-in user — on the canvas
       * rather than on the plane they belong to.
       *
       * `sticky top-0 h-screen` rather than a scrolling column: the plane stays
       * where the user left it while the canvas scrolls under it, which is what
       * makes it read as a fixed part of the product rather than as page
       * content that happens to be dark.
       *
       * Hidden below `md`, where the drawer carries the same three regions.
       * Exactly one `Main` navigation landmark is exposed at any width: this
       * one is `display: none` below `md`, and the drawer's lives inside a
       * closed `<dialog>`, which is absent from the accessibility tree.
       */}
      <aside className="hidden bg-nav-surface md:sticky md:top-0 md:flex md:h-screen md:w-(--rail-width) md:shrink-0 md:flex-col">
        <div className="flex h-16 shrink-0 items-center px-5">
          <ShellIdentity asLink />
        </div>

        {/* `min-h-0` so a long list scrolls inside the rail rather than
            stretching it past the viewport and taking the user menu with it. */}
        <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-4">
          <SidebarNav />
        </div>

        <div className="shrink-0 px-3 pb-5">
          <UserMenu email={profile.email} />
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {/*
         * Mobile only. Below `md` there is no rail, so this carries the drawer
         * trigger and the product identity — and nothing else. Identity and
         * sign-out live inside the drawer, where a real address has a column's
         * width instead of a header's leftovers.
         */}
        <header className="flex items-center gap-3 border-b border-border bg-surface px-4 py-2 md:hidden">
          <MobileNav identity={<UserMenu email={profile.email} />} />

          <Link href="/dashboard" className="text-base font-semibold tracking-tight text-text">
            ProjectOne
          </Link>
        </header>

        {/*
         * `tabIndex={-1}` is what makes the skip link actually move focus.
         * Without it the fragment scrolls the landmark into view and leaves
         * focus on `<body>`, so the next Tab returns the user to the top of
         * the navigation — the skip link appears to work and does not.
         * Negative, so it is a focus TARGET without joining the tab order
         * (§9.1 rule 4 forbids a positive tabIndex; -1 is not one).
         *
         * `min-w-0` is what lets this actually shrink. A flex item defaults to
         * `min-width: auto`, which refuses to go below its content — so beside
         * the rail at `md` a wide section pushed the document past the viewport
         * and the page scrolled horizontally, which §9a rule 4 forbids.
         */}
        <main id="main-content" tabIndex={-1} className="min-w-0 flex-1 px-6 py-8">
          {children}
        </main>
      </div>
    </div>
  );
}
