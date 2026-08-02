import Link from "next/link";

import { SidebarNav } from "@/components/shell/SidebarNav";

/**
 * The authenticated application shell.
 *
 * A route group (`(app)`) rather than a path segment: it wraps every
 * application screen in this chrome without adding `/app` to any URL. Feature
 * steps add route segments inside it and inherit the shell for free.
 *
 * A Server Component. The only client code beneath it is {@link SidebarNav},
 * which needs the pathname to mark the active route — everything else here
 * renders on the server and ships no JavaScript.
 *
 * Authentication is deliberately NOT enforced here. Session handling arrives
 * with [[STEP-16 Sign Up and Sign In UI]]; gating routes before it exists would
 * be a guess at a contract that has not been built. There is nothing to protect
 * yet — every screen inside is a placeholder.
 */
export default function AppLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <div className="flex min-h-screen flex-col">
      {/*
       * A skip link is the difference between a keyboard user reaching the
       * content in one keystroke and tabbing through every nav item on every
       * page. Visually hidden until focused.
       */}
      <a
        href="#main-content"
        className="sr-only rounded-md bg-surface-raised px-4 py-2 text-sm font-medium text-accent focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50"
      >
        Skip to content
      </a>

      <header className="flex items-center gap-4 border-b border-border bg-surface px-6 py-3">
        <Link href="/dashboard" className="text-base font-semibold text-text">
          ProjectOne
        </Link>
      </header>

      <div className="flex flex-1 flex-col md:flex-row">
        <aside className="border-b border-border bg-surface px-4 py-4 md:w-56 md:shrink-0 md:border-b-0 md:border-r">
          <SidebarNav />
        </aside>

        <main id="main-content" className="flex-1 px-6 py-8">
          {children}
        </main>
      </div>
    </div>
  );
}
