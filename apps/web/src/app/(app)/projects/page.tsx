import type { Metadata } from "next";
import Link from "next/link";

import { FormField } from "@/components/auth/FormField";
import { StatusBadge } from "@/components/projects/StatusBadge";
import { SettingsForm } from "@/components/settings/SettingsForm";
import { SettingsSection } from "@/components/settings/SettingsSection";
import { EmptyState } from "@/components/shell/EmptyState";
import { type ApiProject, listProjects } from "@/lib/api";
import { requireProfile, resolveAccessToken } from "@/lib/auth";
import { resolveWorkspace } from "@/lib/workspace";
import { PageHeader } from "@/components/shell/PageHeader";

import { createProjectAction } from "./actions";

export const metadata: Metadata = {
  title: "Projects — ProjectOne",
};

/**
 * The projects list: every project in the current workspace, and a form to add
 * one.
 *
 * A **Server Component**. Every value on this page is fetched and rendered
 * server-side; the only client code beneath it is the create form's shell. The
 * access token lives in an httpOnly cookie the browser cannot read, so a client
 * component could not fetch any of this even if it wanted to (CLAUDE.md §11).
 *
 * ## Archived projects are listed, not hidden
 *
 * Archive is a lifecycle state, not a deletion — an archived project is still
 * part of the workspace and still holds its assets. Filtering it out of this
 * list would make archiving *look* like deleting, which is precisely the
 * confusion [[Project Lifecycle#Archive Is Not Deletion]] warns against. The
 * badge distinguishes them instead.
 */
export default async function ProjectsPage() {
  await requireProfile();

  const accessToken = await resolveAccessToken();
  const workspace = accessToken === undefined ? undefined : await resolveWorkspace(accessToken);

  if (accessToken === undefined || workspace === undefined) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader title="Projects" />
        <EmptyState
          title="No workspace yet"
          description="Projects live inside a workspace. Once you belong to one, your projects appear here."
        />
      </div>
    );
  }

  const workspaceId = workspace.current.id;
  const projects = await listProjects(accessToken, workspaceId);

  return (
    <ProjectsScreen
      workspaceId={workspaceId}
      workspaceName={workspace.current.name}
      otherWorkspaceCount={workspace.available.length - 1}
      projects={projects}
    />
  );
}

interface ProjectsScreenProps {
  readonly workspaceId: string;
  readonly workspaceName: string;
  readonly otherWorkspaceCount: number;
  readonly projects: readonly ApiProject[];
}

/**
 * The rendered screen, separated from the data fetching above it.
 *
 * The same split the settings screen uses: the layout is readable without the
 * awaits, and a future test can render it against fixed props.
 */
function ProjectsScreen({
  workspaceId,
  workspaceName,
  otherWorkspaceCount,
  projects,
}: ProjectsScreenProps) {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Projects"
        description={
          <>
            The work in {workspaceName}.
            {/*
             * The multi-workspace limitation, disclosed rather than hidden —
             * inherited from STEP-19 and still true: the application resolves the
             * caller's first workspace and has no switcher. See `lib/workspace.ts`.
             */}
            {otherWorkspaceCount > 0
              ? ` You belong to ${otherWorkspaceCount} other ${
                  otherWorkspaceCount === 1 ? "workspace" : "workspaces"
                } — switching between them is not available yet.`
              : ""}
          </>
        }
      />

      <SettingsSection
        title="New project"
        description="Every project starts as an idea and moves through the pipeline from there."
      >
        <SettingsForm
          action={createProjectAction}
          submitLabel="Create project"
          pendingLabel="Creating…"
          savedLabel="Created"
          hidden={{ workspace_id: workspaceId }}
        >
          <div className="flex flex-col gap-4">
            <FormField
              id="project-name"
              name="name"
              label="Name"
              type="text"
              autoComplete="off"
              placeholder="Spring campaign"
            />

            <FormField
              id="project-description"
              name="description"
              label="Description"
              type="text"
              autoComplete="off"
              placeholder="What this project is for"
              hint="Optional."
            />
          </div>
        </SettingsForm>
      </SettingsSection>

      {projects.length === 0 ? (
        <EmptyState
          title="No projects yet"
          description="Projects group your scripts, media and published work. Create one above to get started."
        />
      ) : (
        <section aria-labelledby="all-projects-heading" className="flex flex-col gap-3">
          <h2 id="all-projects-heading" className="text-lg font-medium text-text">
            All projects
          </h2>

          <ul className="flex flex-col gap-3">
            {projects.map((project) => (
              <li key={project.id}>
                <ProjectCard project={project} />
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

/**
 * One project in the list.
 *
 * The whole card is a link rather than a card containing a link: a small "View"
 * target beside a large inert region is harder to hit and gives a keyboard user
 * one tiny stop instead of one obvious one.
 */
function ProjectCard({ project }: { readonly project: ApiProject }) {
  return (
    <Link
      href={`/projects/${project.id}`}
      className="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-border bg-surface px-6 py-5 transition-colors hover:bg-surface-raised"
    >
      <div className="flex flex-col gap-1">
        <span className="text-base font-medium text-text">{project.name}</span>
        {project.description !== null ? (
          <span className="max-w-prose text-sm text-text-muted">{project.description}</span>
        ) : null}
      </div>

      <StatusBadge status={project.status} />
    </Link>
  );
}
