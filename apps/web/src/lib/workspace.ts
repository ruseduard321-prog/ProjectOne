/**
 * Which workspace the application is currently acting in.
 *
 * ## The decision this module encodes, and its boundary
 *
 * Every settings screen is workspace-scoped, and until this step the web
 * application had **no concept of a workspace at all** — nothing read
 * `GET /workspaces`, and the shell showed only the signed-in user. So STEP-19
 * had to answer "which workspace?" before it could render anything.
 *
 * **The answer is: the caller's first workspace, resolved server-side on each
 * request.** A workspace *switcher* — persisted selection, a picker in the
 * shell, URLs that carry the workspace — is a real feature with real
 * requirements, and building it here would be scope this step does not have
 * (CLAUDE.md §29, §35). It belongs with [[STEP-20 Projects Schema and
 * Lifecycle]] onward, where a second workspace first becomes something a user
 * routinely has.
 *
 * The consequence is stated plainly rather than hidden: **a user who belongs to
 * more than one workspace can currently only configure the first.** That is a
 * limitation, not a defect, and it is visible on the screen rather than silent —
 * `resolveWorkspace` returns the full list so the UI can say which workspace it
 * is showing and how many others exist.
 *
 * ## Why ordering is not left implicit
 *
 * `GET /workspaces` orders by name, so "first" is stable across requests rather
 * than being whatever the database returned that time. A selection that silently
 * moved between page loads would be far worse than one that is fixed and
 * disclosed.
 *
 * Server-only, like everything that touches the session.
 */

import { type ApiWorkspace, listWorkspaces } from "@/lib/api";

/** The workspace being acted in, and what else the caller could have chosen. */
export interface ResolvedWorkspace {
  /** The workspace the screens operate on. */
  readonly current: ApiWorkspace;
  /**
   * Every workspace the caller belongs to, in the API's stable name order.
   *
   * Carried so a screen can disclose that a selection was made on the user's
   * behalf. A count alone would be cheaper and would not let the UI name the
   * others, which is the part that makes the limitation honest.
   */
  readonly available: readonly ApiWorkspace[];
}

/**
 * Resolve the workspace the settings screens act on.
 *
 * @returns The resolution, or `undefined` when the caller belongs to no
 *   workspace at all. That is a legitimate state rather than an error — a user
 *   whose email confirmation completed but who never created a workspace is in
 *   it — so it is modelled and rendered as an empty state, not thrown.
 */
export async function resolveWorkspace(
  accessToken: string,
): Promise<ResolvedWorkspace | undefined> {
  const workspaces = await listWorkspaces(accessToken);

  const current = workspaces[0];

  if (current === undefined) {
    return undefined;
  }

  return { current, available: workspaces };
}
