import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { FormField } from "@/components/auth/FormField";
import { AssetKindField } from "@/components/projects/AssetKindField";
import { AssetList } from "@/components/projects/AssetList";
import { AssetUpload } from "@/components/projects/AssetUpload";
import { StatusBadge } from "@/components/projects/StatusBadge";
import { TransitionControls } from "@/components/projects/TransitionControls";
import { SettingsForm } from "@/components/settings/SettingsForm";
import { SettingsSection } from "@/components/settings/SettingsSection";
import { type ApiAsset, type ApiProject, ApiError, listAssets, readProject } from "@/lib/api";
import { requireProfile, resolveAccessToken } from "@/lib/auth";
import { resolveWorkspace } from "@/lib/workspace";
import { PageHeader } from "@/components/shell/PageHeader";

import {
  assetDownloadUrlAction,
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

        {/*
         * The status is page-level state rather than a control, so it sits in
         * the header's action slot: it belongs beside the title, and putting
         * it there means this screen states its shape with the same primitive
         * every other screen uses instead of rebuilding the row by hand.
         */}
        <PageHeader
          title={project.name}
          description={project.description ?? undefined}
          actions={<StatusBadge status={project.status} />}
        />
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
          <AssetList
            workspaceId={workspaceId}
            projectId={project.id}
            assets={assets}
            deleteAction={deleteAssetAction}
            mint={assetDownloadUrlAction}
          />

          <div className="flex flex-col gap-4 border-t border-border pt-6">
            <h3 className="text-sm font-medium text-text">Upload a file</h3>
            <AssetUpload workspaceId={workspaceId} projectId={project.id} />
          </div>

          {/*
           * The metadata-only form stays alongside the upload ([[STEP-29 Asset
           * Management UI]] D5). The API's two asset routes are both useful —
           * an asset can be planned before the file exists — so removing this
           * would delete a capability this screen already had. The two are
           * worded to say plainly which is which, because two controls that
           * look like two ways to do one thing is the real risk of keeping both.
           */}
          <div className="flex flex-col gap-4 border-t border-border pt-6">
            <h3 className="text-sm font-medium text-text">Record an asset without a file</h3>

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
                    hint="Records a placeholder. Add the file later by uploading it."
                  />
                </div>
              </div>
            </SettingsForm>
          </div>
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
