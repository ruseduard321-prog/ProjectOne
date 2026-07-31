import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Health — ProjectOne",
  description: "Static health indicator for the ProjectOne web application.",
};

/**
 * Static health indicator.
 *
 * Deliberately a Server Component with no data fetching, no state and no
 * client JavaScript: its only job is to prove the app builds, routes and
 * renders. Liveness/readiness probes that query real dependencies belong to
 * the API app, not here.
 */
export default function HealthPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-3 p-8">
      <h1 className="text-2xl font-semibold tracking-tight">ProjectOne</h1>
      <p
        className="rounded-full border border-emerald-600/30 bg-emerald-500/10 px-4 py-1.5 text-sm font-medium text-emerald-700 dark:text-emerald-400"
        role="status"
      >
        Web application is running
      </p>
    </main>
  );
}
