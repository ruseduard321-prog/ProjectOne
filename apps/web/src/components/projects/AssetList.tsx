import { AssetRow } from "@/components/projects/AssetRow";
import { EmptyState } from "@/components/shell/EmptyState";
import type { ApiAsset } from "@/lib/api";
import type { FormState } from "@/lib/form-state";
import type { AssetUrlResult } from "@/lib/projects";

/**
 * Every asset attached to a project, or an honest account of there being none.
 *
 * A **Server Component**: the list is data the server already has, and rendering
 * it here keeps it out of the client bundle entirely.
 *
 * ## Empty is not error
 *
 * This component renders only the *empty* state. A failure to load the assets is
 * not represented here at all — the page's `listAssets` call throws, and either
 * `notFound()` or the route's error boundary answers it. That separation is
 * [[Design System]] §10 rule 2: "no assets yet" and "we could not load your
 * assets" require different words and different actions, and showing the first
 * when the second is true is a lie about the system.
 */
export interface AssetListProps {
  readonly workspaceId: string;
  readonly projectId: string;
  readonly assets: readonly ApiAsset[];
  readonly deleteAction: (previous: FormState, data: FormData) => Promise<FormState>;
  readonly mint: (
    workspaceId: string,
    projectId: string,
    assetId: string,
  ) => Promise<AssetUrlResult>;
}

export function AssetList({
  workspaceId,
  projectId,
  assets,
  deleteAction,
  mint,
}: AssetListProps) {
  if (assets.length === 0) {
    return (
      <EmptyState
        title="No assets yet"
        description="Upload a file, or record an asset you plan to add later. Both appear here."
      />
    );
  }

  return (
    <ul className="flex flex-col gap-3">
      {assets.map((asset) => (
        <AssetRow
          key={asset.id}
          workspaceId={workspaceId}
          projectId={projectId}
          asset={asset}
          deleteAction={deleteAction}
          mint={mint}
        />
      ))}
    </ul>
  );
}
