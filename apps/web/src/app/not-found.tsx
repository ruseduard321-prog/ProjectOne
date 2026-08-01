import Link from "next/link";

/**
 * Root not-found state.
 *
 * Required by [[Chapter 05 - NextJS Architecture]] §5.9. A Server Component:
 * nothing here needs browser APIs or interactive state.
 */
export default function NotFound() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-3 p-8">
      <h1 className="text-2xl font-semibold tracking-tight text-text">
        Page not found
      </h1>
      <p className="text-sm text-text-muted">
        The page you are looking for does not exist.
      </p>
      <Link
        href="/"
        className="text-sm text-accent underline underline-offset-4"
      >
        Return home
      </Link>
    </main>
  );
}
