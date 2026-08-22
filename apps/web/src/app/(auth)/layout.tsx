import Link from "next/link";

import { PageTemplate } from "@/components/shell/PageTemplate";

/**
 * The layout for unauthenticated screens.
 *
 * A separate route group from `(app)` deliberately: sign-up and sign-in must
 * not render the application's nav chrome, because every destination in it
 * requires the session the visitor does not have yet. Offering a sidebar full
 * of links that all bounce back here is a worse experience than not offering it.
 *
 * Neither group adds a URL segment, so these screens live at `/sign-in` and
 * `/sign-up` rather than under a prefix.
 *
 * A Server Component with no client code beneath it except the form itself.
 *
 * **Focus** — narrow single column, reduced chrome, one task (ADR-007
 * Decision 8). Signing in is the clearest instance of the shape the template
 * describes, and the surface already had its own measure hardcoded here; it
 * now states which template it is rather than reinventing one.
 */
export default function AuthLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-border bg-surface px-6 py-3">
        <Link href="/" className="text-base font-semibold text-text">
          ProjectOne
        </Link>
      </header>

      <main className="flex flex-1 items-center justify-center px-6 py-12">
        <PageTemplate template="focus">
          {/*
           * A sign-in form is narrower than the Focus measure, which is sized
           * for reading rather than for a two-field form. The template caps the
           * column; this centres the form inside it.
           */}
          <div className="mx-auto w-full max-w-sm">{children}</div>
        </PageTemplate>
      </main>
    </div>
  );
}
