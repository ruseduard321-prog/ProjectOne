import type { Metadata } from "next";

import { env } from "@/lib/env";

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
 *
 * It reads {@link env} so validated configuration is exercised on a real
 * route rather than sitting unused — a config layer nothing imports is a
 * config layer nobody notices is broken.
 */
export default function HealthPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-3 p-8">
      <h1 className="text-2xl font-semibold tracking-tight text-text">
        ProjectOne
      </h1>
      <p
        className="rounded-full border border-success bg-surface px-4 py-2 text-sm font-medium text-success"
        role="status"
      >
        Web application is running
      </p>
      <p className="text-sm text-text-muted">
        Environment: <span className="font-medium">{env.environment}</span>
      </p>
    </main>
  );
}
