import type { Metadata } from "next";

import { EmptyState } from "@/components/shell/EmptyState";

export const metadata: Metadata = {
  title: "Dashboard — ProjectOne",
};

/**
 * Dashboard route placeholder.
 *
 * The real dashboard is [[STEP-24 Dashboard]]. This exists so the shell's
 * routing structure is real and navigable rather than a set of dead links —
 * and so later steps add content to an existing segment instead of
 * restructuring one.
 */
export default function DashboardPage() {
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold tracking-tight text-text">
        Dashboard
      </h1>
      <EmptyState
        title="Nothing to show yet"
        description="Your activity, usage and recent work will appear here once there is something to report."
      />
    </div>
  );
}
