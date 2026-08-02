import Link from "next/link";

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
        <div className="w-full max-w-sm">{children}</div>
      </main>
    </div>
  );
}
