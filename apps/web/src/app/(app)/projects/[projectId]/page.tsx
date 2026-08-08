import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { FormField } from "@/components/auth/FormField";
import { AssetKindField } from "@/components/projects/AssetKindField";
import { StatusBadge } from "@/components/projects/StatusBadge";
import { TransitionControls } from "@/components/projects/TransitionControls";
import { SettingsForm } from "@/components/settings/SettingsForm";
import { SettingsSection } from "@/components/settings/SettingsSection";
import { EmptyState } from "@/components/shell/EmptyState";
import { type ApiAsset, type ApiProject, ApiError, listAssets, readProject } from "@/lib/api";
import { requireProfile, resolveAccessToken } from "@/lib/auth";
import { assetKindLabel } from "@/lib/projects";
import { resolveWorkspace } from "@/lib/workspace";

import {
  createAssetAction,
  deleteAssetAction,
  deleteProjectAction,
  renameProjectAction,
  transitionProjectAction,
} from "../actions";

export const metadata: Metadata = {
  title: "Project — ProjectOne",
};

/**
 * One project: its status, the moves it can make, its details and its assets.
 *
 * A **Server Component**. The only client code beneath it is the form shells and
 * the transition buttons, each of which needs pending state.
 *
 * ## A project the caller cannot see renders as not-found
 *
 * The API answers **404** for a project in another workspace — deliberately the
 * same answer as one that does not exist, so a project id cannot be used to
 * probe across tenants (`app/core/errors.py`). This page converts that into
 * Next's `notFound()`, which renders the not-found page rather than the error
 * boundary: "this project does not exist" is a normal outcome of following a
 * stale link, not a failure.
 *
 * Every other status still throws, and is caught by the route's error boundary.
 */
export default async function ProjectDetailPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;

  await requireProfile();

  const accessToken = await resolveAccessToken();
  const workspace = accessToken === undefined ? undefined : await resolveWorkspace(accessToken);

  if (accessToken === undefined || workspace === undefined) {
    notFound();
  }

  const workspaceId = workspace.current.id;

  let project: ApiProject;
  let assets: readonly ApiAsset[];

  try {
    // Sequential rather than concurrent, unlike the settings screen: the asset
    // list is only meaningful if the project exists, and issuing both at once
    // would mean a 404 on the project raced against a second request that can
    // only fail the same way.
    project = await readProject(accessToken, workspaceId, projectId);
    assets = await listAssets(accessToken, workspaceId, projectId);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      notFound();
    }

    throw error;
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3">
        <Link href="/projects" className="text-sm text-text-muted underline underline-offset-4">
          ← All projects
        </Link>

        <div className="flex flex-wrap items-start justify-between gap-3">
          <h1 className="text-2xl font-semibold tracking-tight text-text">{project.name}</h1>
          <StatusBadge status={project.status} />
        </div>

        {project.description !== null ? (
          <p className="max-w-prose text-sm text-text-muted">{project.description}</p>
        ) : null}
      </div>

      <SettingsSection
        title="Lifecycle"
        description="Where this project is, and where it can go next."
      >
        {/*
         * The buttons come from `project.legal_transitions` — the server's own
         * answer for this project in this state. The frontend holds no copy of
         * the transition rules; see `components/projects/TransitionControls.tsx`.
         */}
        <TransitionControls
          workspaceId={workspaceId}
          projectId={project.id}
          legalTransitions={project.legal_transitions}
          action={transitionProjectAction}
        />
      </SettingsSection>

      <SettingsSection title="Details" description="The name and description everyone sees.">
        <SettingsForm
          action={renameProjectAction}
          submitLabel="Save details"
          pendingLabel="Saving…"
          hidden={{ workspace_id: workspaceId, project_id: project.id }}
        >
          <div className="flex flex-col gap-4">
            <FormField
              id="project-name"
              name="name"
              label="Name"
              type="text"
              autoComplete="off"
              defaultValue={project.name}
            />

            <FormField
              id="project-description"
              name="description"
              label="Description"
              type="text"
              autoComplete="off"
              defaultValue={project.description ?? ""}
              hint="Leave blank to clear it."
            />
          </div>
        </SettingsForm>
      </SettingsSection>

      <SettingsSection
        title="Assets"
        description="The scripts, media and files that belong to this project."
      >
        <div className="flex flex-col gap-6">
          {assets.length === 0 ? (
            <EmptyState
              title="No assets yet"
              description="Record the scripts, thumbnails and media this project needs. Uploading files is not available yet."
            />
          ) : (
            <ul className="flex flex-col gap-3">
              {assets.map((asset) => (
                <li
                  key={asset.id}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border px-4 py-3"
                >
                  <div className="flex flex-col gap-1">
                    <span className="text-sm font-medium text-text">{asset.name}</span>
                    <span className="text-xs text-text-muted">
                      {assetKindLabel(asset.kind)}
                    </span>
                  </div>

                  <SettingsForm
                    action={deleteAssetAction}
                    submitLabel="Remove"
                    pendingLabel="Removing…"
                    savedLabel="Removed"
                    intent="danger"
                    hidden={{
                      workspace_id: workspaceId,
                      project_id: project.id,
                      asset_id: asset.id,
                    }}
                  >
                    {/* No fields: the hidden inputs above carry the whole payload. */}
                    {null}
                  </SettingsForm>
                </li>
              ))}
            </ul>
          )}

          <SettingsForm
            action={createAssetAction}
            submitLabel="Add asset"
            pendingLabel="Adding…"
            savedLabel="Added"
            hidden={{ workspace_id: workspaceId, project_id: project.id }}
          >
            <div className="flex flex-col gap-4 sm:flex-row sm:gap-4">
              <div className="flex-1">
                <FormField
                  id="asset-name"
                  name="name"
                  label="Asset name"
                  type="text"
                  autoComplete="off"
                  placeholder="Opening script"
                />
              </div>

              <div className="flex-1">
                <AssetKindField
                  id="asset-kind"
                  name="kind"
                  label="Kind"
                  /*
                   * Stated plainly rather than discovered: this records that an
                   * asset exists, it does not store a file. No storage backend
                   * is chosen yet — that needs an ADR (CLAUDE.md §10/§28).
                   */
                  hint="Records the asset. File upload is not available yet."
                />
              </div>
            </div>
          </SettingsForm>
        </div>
      </SettingsSection>

      <SettingsSection
        title="Delete project"
        description="Removes this project from the workspace. Archiving keeps it as a record instead — they are not the same thing."
      >
        <SettingsForm
          action={deleteProjectAction}
          submitLabel="Delete project"
          pendingLabel="Deleting…"
          savedLabel="Deleted"
          intent="danger"
          hidden={{ workspace_id: workspaceId, project_id: project.id }}
        >
          {/* No fields: the hidden inputs above carry the whole payload. */}
          {null}
        </SettingsForm>
      </SettingsSection>
    </div>
  );
}
