import type { Metadata } from "next";

import { EmptyState } from "@/components/shell/EmptyState";

export const metadata: Metadata = {
  title: "Projects — ProjectOne",
};

/**
 * Projects route placeholder.
 *
 * The real screen is [[STEP-21 Projects UI]], backed by the schema in
 * [[STEP-20 Projects Schema and Lifecycle]]. Placeholder only — no data access
 * exists yet.
 */
export default function ProjectsPage() {
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold tracking-tight text-text">
        Projects
      </h1>
      <EmptyState
        title="No projects yet"
        description="Projects group your scripts, media and published work. Creating them arrives with the projects release."
      />
    </div>
  );
}
