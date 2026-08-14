/**
 * The workflow-runs client surface (STEP-24).
 *
 * The web application had no workflow client at all before this step, while the
 * API had exposed `GET /workspaces/{id}/workflows/runs` since STEP-22. These
 * assert the properties of consuming an endpoint that already existed:
 *
 * - **The workspace id is a path segment, never a body or query field.** The API
 *   authorizes against the path, so a tenant id supplied anywhere else would be
 *   a caller choosing their own permission check.
 * - **The call sends no pagination parameters**, because the endpoint takes
 *   none — it is bounded by the repository's own limit. A client inventing
 *   `?limit=` would be a client describing a contract the server does not have.
 * - **Failures surface as `ApiError`**, carrying the envelope's message and
 *   correlation id, so the dashboard's error boundary has something to report.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, type ApiWorkflowRun, listWorkflowRuns } from "@/lib/api";

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

/** A run as the API returns it, with its steps carried on the run itself. */
const RUN: ApiWorkflowRun = {
  id: "11111111-1111-1111-1111-111111111111",
  workspace_id: "22222222-2222-2222-2222-222222222222",
  workflow_type: "script_draft",
  definition_version: 1,
  status: "awaiting_approval",
  project_id: null,
  detail: "Waiting on approval for step 2",
  triggered_by: "33333333-3333-3333-3333-333333333333",
  started_at: "2026-08-12T10:00:00+00:00",
  finished_at: null,
  created_at: "2026-08-12T09:59:00+00:00",
  steps: [
    {
      step_index: 0,
      step_name: "draft",
      status: "completed",
      detail: null,
      tokens_used: 412,
      started_at: "2026-08-12T10:00:00+00:00",
      finished_at: "2026-08-12T10:00:20+00:00",
    },
  ],
};

describe("reading recent runs", () => {
  it("addresses the endpoint beneath the workspace it reads", async () => {
    const calls = capture([RUN]);

    await listWorkflowRuns("token", "workspace-1");

    expect(calls).toHaveLength(1);
    expect(calls[0]?.url).toBe(
      "http://127.0.0.1:8000/api/v1/workspaces/workspace-1/workflows/runs",
    );
    expect(calls[0]?.init.method).toBe("GET");
  });

  it("sends no pagination parameters, because the endpoint takes none", () => {
    const calls = capture([RUN]);

    return listWorkflowRuns("token", "workspace-1").then(() => {
      expect(calls[0]?.url).not.toContain("?");
    });
  });

  it("authenticates with the bearer token", async () => {
    const calls = capture([]);

    await listWorkflowRuns("token-abc", "workspace-1");

    const headers = calls[0]?.init.headers as Record<string, string>;

    expect(headers.Authorization).toBe("Bearer token-abc");
  });

  it("returns the runs with their steps intact", async () => {
    // The steps ride on the run rather than arriving from a second endpoint, so
    // a client rendering a run always has the history that explains its state.
    capture([RUN]);

    const runs = await listWorkflowRuns("token", "workspace-1");

    expect(runs).toHaveLength(1);
    expect(runs[0]?.status).toBe("awaiting_approval");
    expect(runs[0]?.steps).toHaveLength(1);
    expect(runs[0]?.steps[0]?.step_name).toBe("draft");
  });

  it("carries a null start time for a run that has not begun", async () => {
    // The nullability the dashboard's timestamp rule depends on. If this ever
    // stopped being nullable, the fallback would become unreachable code.
    capture([{ ...RUN, status: "pending", started_at: null }]);

    const runs = await listWorkflowRuns("token", "workspace-1");

    expect(runs[0]?.started_at).toBeNull();
    expect(runs[0]?.created_at).toBe("2026-08-12T09:59:00+00:00");
  });

  it("returns an empty list for a workspace that has run nothing", async () => {
    capture([]);

    expect(await listWorkflowRuns("token", "workspace-1")).toEqual([]);
  });

  it("raises ApiError with the envelope's message and correlation id", async () => {
    capture({ detail: "Not a member of this workspace", request_id: "req-42" }, 403);

    await expect(listWorkflowRuns("token", "workspace-1")).rejects.toThrow(ApiError);

    capture({ detail: "Not a member of this workspace", request_id: "req-42" }, 403);

    await listWorkflowRuns("token", "workspace-1").catch((error: unknown) => {
      expect(error).toBeInstanceOf(ApiError);
      expect((error as ApiError).status).toBe(403);
      expect((error as ApiError).requestId).toBe("req-42");
      expect((error as ApiError).message).toBe("Not a member of this workspace");
    });
  });
});
