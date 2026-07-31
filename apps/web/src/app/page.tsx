import Link from "next/link";

/**
 * Placeholder root route.
 *
 * The real application shell arrives in STEP-15; this exists only so the app
 * has a valid entry point and is not serving framework boilerplate.
 */
export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-3 p-8">
      <h1 className="text-2xl font-semibold tracking-tight">ProjectOne</h1>
      <p className="text-sm opacity-70">
        An AI Operating System for content businesses.
      </p>
      <Link href="/health" className="text-sm underline underline-offset-4">
        Health
      </Link>
    </main>
  );
}
