import { AssetPreview } from "@/components/projects/AssetPreview";
import { SettingsForm } from "@/components/settings/SettingsForm";
import { ConfirmDialog } from "@/components/shell/ConfirmDialog";
import type { ApiAsset } from "@/lib/api";
import type { FormState } from "@/lib/form-state";
import { type AssetUrlResult, assetKindLabel } from "@/lib/projects";

/**
 * One asset in a project's list.
 *
 * A **Server Component**. Only the two controls beneath it need the browser —
 * the preview, which mints a URL on click, and the confirmation dialog. The row
 * itself, its name and its labels are rendered on the server and never shipped.
 *
 * ## An asset with no file is a state, not a failure
 *
 * `storage_path` is null for an asset recorded through the metadata-only form,
 * which is a legitimate thing to do: an asset can be planned before it exists
 * (`app/routers/projects.py`). Such a row renders as *no file attached* with no
 * preview control at all — not as a broken preview, and not as an error. It is
 * also the only thing this component reads from that column: the value itself is
 * opaque and must never be parsed, split, prefixed or displayed (ADR-004).
 */
export interface AssetRowProps {
  readonly workspaceId: string;
  readonly projectId: string;
  readonly asset: ApiAsset;
  /** Removes the asset. Supplied by the page, as `TransitionControls` does. */
  readonly deleteAction: (previous: FormState, data: FormData) => Promise<FormState>;
  /** Mints a signed URL for the preview control. */
  readonly mint: (
    workspaceId: string,
    projectId: string,
    assetId: string,
  ) => Promise<AssetUrlResult>;
}

export function AssetRow({ workspaceId, projectId, asset, deleteAction, mint }: AssetRowProps) {
  const hasFile = asset.storage_path !== null;

  return (
    <li className="flex flex-col gap-3 rounded-md border border-border px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-col gap-1">
          <span className="text-sm font-medium text-text">{asset.name}</span>
          <span className="text-xs text-text-muted">
            {assetKindLabel(asset.kind)}
            {hasFile ? null : " · No file attached"}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {hasFile ? (
            <AssetPreview
              workspaceId={workspaceId}
              projectId={projectId}
              assetId={asset.id}
              assetName={asset.name}
              kind={asset.kind}
              mint={mint}
            />
          ) : null}

          <ConfirmDialog
            triggerLabel="Remove"
            title="Remove this asset?"
            description={`“${asset.name}” will be removed from this project${
              hasFile ? ", and its file will no longer be reachable" : ""
            }. This cannot be undone.`}
          >
            <SettingsForm
              action={deleteAction}
              submitLabel="Remove asset"
              pendingLabel="Removing…"
              savedLabel="Removed"
              intent="danger"
              hidden={{
                workspace_id: workspaceId,
                project_id: projectId,
                asset_id: asset.id,
              }}
            >
              {/* No fields: the hidden inputs above carry the whole payload. */}
              {null}
            </SettingsForm>
          </ConfirmDialog>
        </div>
      </div>
    </li>
  );
}
