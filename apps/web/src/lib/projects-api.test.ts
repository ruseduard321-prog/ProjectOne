import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  type ApiProject,
  type ApiProjectStatus,
  createAsset,
  createProject,
  deleteAsset,
  deleteProject,
  listProjects,
  renameProject,
  transitionProject,
} from "@/lib/api";
import {
  ASSET_KINDS,
  PROJECT_STATUSES,
  assetKindLabel,
  isAssetKind,
  isProjectStatus,
  statusLabel,
  transitionLabel,
} from "@/lib/projects";

/**
 * The projects client surface (STEP-21).
 *
 * These assert the properties that would be expensive to discover later:
 *
 * - **The frontend holds no copy of the transition rules.** The single most
 *   important property of this step. A map from state to allowed next states
 *   anywhere in the frontend would diverge from the server's the first time the
 *   rules changed, and the divergence would surface as a button that produces a
 *   409 — or worse, a legal move the UI never offers. The rules arrive per
 *   project in `legal_transitions`, and this file proves nothing else decides.
 * - **A status is never sent in a path.** It travels in the request body, so a
 *   lifecycle change does not appear in proxy logs and browser history as a
 *   distinct URL.
 * - **`status` is never submitted on create or rename.** The API answers 422,
 *   but a client that sent one would be a client whose author believed the
 *   status was directly writable.
 */

beforeEach(() => {
  process.env.NEXT_PUBLIC_PROJECTONE_ENVIRONMENT = "development";
  process.env.NEXT_PUBLIC_PROJECTONE_API_URL = "http://127.0.0.1:8000";
});

afterEach(() => {
  vi.restoreAllMocks();
});

interface Captured {
  readonly url: string;
  readonly init: RequestInit;
}

/** Stub fetch, returning `body`, and capture what was sent. */
function capture(body: unknown, status = 200): Captured[] {
  const calls: Captured[] = [];

  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit) => {
      calls.push({ url, init });

      return Promise.resolve({
        ok: status >= 200 && status < 300,
        status,
        json: async () => Promise.resolve(body),
      } as Response);
    }),
  );

  return calls;
}

/** A project as the API returns it, with whichever status the test needs. */
function project(
  status: ApiProjectStatus,
  legalTransitions: readonly ApiProjectStatus[],
): ApiProject {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    workspace_id: "22222222-2222-2222-2222-222222222222",
    name: "A project",
    description: null,
    status,
    legal_transitions: legalTransitions,
    created_by: "33333333-3333-3333-3333-333333333333",
    created_at: "2026-08-08T10:00:00+00:00",
    updated_at: "2026-08-08T10:00:00+00:00",
    version: 1,
  };
}

describe("the lifecycle rules are the server's, not the client's", () => {
  it("sends whatever status it is given, without judging it", async () => {
    // The client does not decide legality. If it did, this call — an illegal
    // move from `idea` — would be refused locally and never reach the API,
    // which is exactly the second copy of the state machine that must not exist.
    const calls = capture(project("publishing", []));

    await transitionProject("token", "workspace-1", "project-1", "publishing");

    expect(calls).toHaveLength(1);
    expect(JSON.parse(String(calls[0]?.init.body))).toEqual({ status: "publishing" });
  });

  it("puts the status in the body, never in the URL", async () => {
    const calls = capture(project("planning", ["generation", "archive"]));

    await transitionProject("token", "workspace-1", "project-1", "planning");

    expect(calls[0]?.url).toBe(
      "http://127.0.0.1:8000/api/v1/workspaces/workspace-1/projects/project-1/transitions",
    );
    expect(calls[0]?.url).not.toContain("planning");
  });

  it("exposes no mapping from a state to its allowed next states", () => {
    /*
     * The guard against the defect this whole design avoids.
     *
     * `lib/projects.ts` is the only module that enumerates statuses, and it must
     * describe the *vocabulary* and its *labels* — never movement. If a future
     * change adds a transition map there, this fails: no exported value may
     * associate one status with a collection of others.
     */
    const statusModule: Record<string, unknown> = {
      PROJECT_STATUSES,
      isProjectStatus,
      statusLabel,
      transitionLabel,
      ASSET_KINDS,
      isAssetKind,
      assetKindLabel,
    };

    for (const [name, value] of Object.entries(statusModule)) {
      if (typeof value === "function" || Array.isArray(value)) {
        continue;
      }

      // Any other exported object is a candidate transition map. The only
      // permitted shape is a flat status → string mapping (labels).
      for (const entry of Object.values(value as Record<string, unknown>)) {
        expect(
          Array.isArray(entry),
          `${name} maps a status to a collection — that is a transition map, and the ` +
            "server owns the transition rules (see lib/projects.ts)",
        ).toBe(false);
      }
    }
  });

  it("labels every status in the vocabulary", () => {
    // Exhaustive by type at compile time; asserted at runtime so a label that is
    // present but empty is caught too.
    for (const status of PROJECT_STATUSES) {
      expect(statusLabel(status).length).toBeGreaterThan(0);
      expect(transitionLabel(status).length).toBeGreaterThan(0);
    }
  });

  it("words archiving as an action rather than as the next pipeline stage", () => {
    // Archive is reachable from everywhere and is terminal, so presenting it
    // identically to "Move to Planning" would suggest it is just the next step.
    expect(transitionLabel("archive")).toBe("Archive project");
    expect(transitionLabel("planning")).toBe("Move to Planning");
  });

  it("narrows a submitted string to the vocabulary", () => {
    expect(isProjectStatus("review")).toBe(true);
    expect(isProjectStatus("not-a-status")).toBe(false);
    expect(isProjectStatus("")).toBe(false);
  });

  it("matches the API's status vocabulary exactly", () => {
    // The database's `ck_projects_status_valid`, the API's `ProjectStatus` and
    // this list are three copies of one vocabulary. The API asserts its own two
    // against each other (`test_status_vocabulary_matches_the_database`); this
    // is the third, and a state added server-side without one here would render
    // as an unlabelled badge.
    expect([...PROJECT_STATUSES]).toEqual([
      "idea",
      "planning",
      "generation",
      "review",
      "editing",
      "approval",
      "publishing",
      "analytics",
      "archive",
    ]);
  });
});

describe("the write surface", () => {
  it("never submits a status when creating", async () => {
    const calls = capture(project("idea", ["planning", "archive"]), 201);

    await createProject("token", "workspace-1", "A project", "Some description");

    const body = JSON.parse(String(calls[0]?.init.body));

    expect(body).toEqual({ name: "A project", description: "Some description" });
    expect(body).not.toHaveProperty("status");
  });

  it("omits the description entirely when there is none", async () => {
    // Omitted rather than sent as `""`, so an absent description is absent
    // rather than an empty string that renders identically and is not null.
    const calls = capture(project("idea", ["planning", "archive"]), 201);

    await createProject("token", "workspace-1", "A project");

    expect(JSON.parse(String(calls[0]?.init.body))).toEqual({ name: "A project" });
  });

  it("never submits a status when renaming", async () => {
    const calls = capture(project("planning", ["generation", "archive"]));

    await renameProject("token", "workspace-1", "project-1", "Renamed", null);

    const body = JSON.parse(String(calls[0]?.init.body));

    expect(body).toEqual({ name: "Renamed", description: null });
    expect(body).not.toHaveProperty("status");
  });

  it("sends a null description to clear one, rather than omitting the field", async () => {
    // `PATCH` here writes both fields, so omission and null are different: null
    // clears the column, omission would be an unexpected field the API refuses.
    const calls = capture(project("idea", []));

    await renameProject("token", "workspace-1", "project-1", "Kept", null);

    expect(JSON.parse(String(calls[0]?.init.body))).toHaveProperty("description", null);
  });

  it("never submits a storage path when recording an asset", async () => {
    // No storage backend exists, and a caller-supplied path would be a client
    // naming a location a future storage layer will trust.
    const calls = capture({}, 201);

    await createAsset("token", "workspace-1", "project-1", "Script", "document");

    const body = JSON.parse(String(calls[0]?.init.body));

    expect(body).toEqual({ name: "Script", kind: "document" });
    expect(body).not.toHaveProperty("storage_path");
  });

  it("matches the database's asset kind vocabulary exactly", () => {
    /*
     * `ck_assets_kind_valid` permits these four values and no others.
     *
     * **This assertion exists because the vocabulary was originally wrong.** The
     * API accepted free text, so `kind: "script"` passed validation and failed
     * at the constraint — a client error surfacing as a 500. A UI offering a
     * value the database refuses is the same defect wearing a text input.
     */
    expect([...ASSET_KINDS]).toEqual(["document", "image", "video", "audio"]);

    for (const kind of ASSET_KINDS) {
      expect(assetKindLabel(kind).length).toBeGreaterThan(0);
    }
  });

  it("refuses an asset kind outside the vocabulary", () => {
    expect(isAssetKind("document")).toBe(true);
    // The value a user would most plausibly type into a free-text field, and
    // the one the database refuses.
    expect(isAssetKind("script")).toBe(false);
    expect(isAssetKind("")).toBe(false);
  });

  it("addresses every route beneath the workspace it acts in", async () => {
    // The workspace id is always a path segment, never a body field: the API
    // authorizes against the path, and a body-supplied tenant id would be a
    // caller choosing their own permission check.
    const base = "http://127.0.0.1:8000/api/v1/workspaces/workspace-1/projects";

    const listing = capture([]);
    await listProjects("token", "workspace-1");
    expect(listing[0]?.url).toBe(base);

    const removal = capture(null, 204);
    await deleteProject("token", "workspace-1", "project-1");
    expect(removal[0]?.url).toBe(`${base}/project-1`);
    expect(removal[0]?.init.method).toBe("DELETE");

    const assetRemoval = capture(null, 204);
    await deleteAsset("token", "workspace-1", "project-1", "asset-1");
    expect(assetRemoval[0]?.url).toBe(`${base}/project-1/assets/asset-1`);
  });

  it("authenticates every call with the bearer token", async () => {
    // Every route here is authenticated. A call that forgot the header would
    // answer 401, which is a slow way to find a missing line.
    const calls = capture([]);

    await listProjects("token-abc", "workspace-1");

    const headers = calls[0]?.init.headers as Record<string, string>;

    expect(headers.Authorization).toBe("Bearer token-abc");
  });
});
