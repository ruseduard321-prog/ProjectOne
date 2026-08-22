/**
 * A stand-in for the ProjectOne API, for browser tests only.
 *
 * ## Why this exists rather than an authentication bypass
 *
 * Every fetch the web application makes runs on the **server**, inside the
 * Next.js process (`lib/api.ts`). Playwright's `page.route()` intercepts the
 * browser's requests, and these requests never reach the browser — so route
 * interception cannot mock them. Something has to answer on a socket.
 *
 * The alternative would have been a test-only branch in `requireProfile` or in
 * `proxy.ts`. That is refused: it would put a way past the authentication gate
 * into production source, controlled by configuration, which is exactly the
 * shape `lib/dev-only.ts` argues against and CLAUDE.md §28a calls a smell.
 *
 * **The production auth path is fully exercised against this stub.** The proxy
 * still checks for a session cookie, `requireProfile()` still resolves a token
 * and still calls `GET /auth/me` with it, and this server still refuses a
 * request that arrives without a bearer token. Only the identity of the API is
 * fake. Nothing in `apps/web/src` knows this file exists.
 *
 * ## What it is not
 *
 * Not a fixture library, not a second implementation of the API, and not a
 * contract test. It returns the smallest well-formed payload each screen needs
 * to render, so the browser suite can assert focus, keyboard, theme and reflow
 * — the things it was added for. It asserts nothing about the real API and
 * proves nothing about it.
 */

import { createServer } from "node:http";

const PORT = Number(process.env.PROJECTONE_STUB_API_PORT ?? 3101);

const WORKSPACE_ID = "11111111-1111-1111-1111-111111111111";
const PROJECT_ID = "22222222-2222-2222-2222-222222222222";
const USER_ID = "33333333-3333-3333-3333-333333333333";
const CONVERSATION_ID = "44444444-4444-4444-4444-444444444444";

/** A fixed instant, so nothing in the suite depends on the wall clock. */
const AT = "2026-08-22T10:00:00+00:00";

const profile = { id: USER_ID, email: "e2e@projectone.test", display_name: "E2E User" };
const workspace = { id: WORKSPACE_ID, name: "E2E Workspace", owner_id: USER_ID };

const project = {
  id: PROJECT_ID,
  workspace_id: WORKSPACE_ID,
  name: "E2E Project",
  description: "A project the browser suite can open.",
  status: "idea",
  /*
   * `planning`, because that is what the API's state machine actually returns
   * from `idea` — one step forward along the lifecycle sequence. The fixture
   * previously said `scripting`, which is not a member of `ApiProjectStatus`
   * at all: `transitionLabel()` looked it up, got `undefined`, and the page
   * rendered "Move to undefined". Found during the 200% zoom audit.
   *
   * A fixture is a contract with the API it stands in for. This one was not
   * type-checked — the stub is plain JavaScript, deliberately, so it can run
   * without a build step — which is why the assertion in `routes.spec.ts`
   * checks the rendered label rather than trusting the payload.
   */
  legal_transitions: ["planning"],
  created_by: USER_ID,
  created_at: AT,
  updated_at: AT,
  version: 1,
};

const conversation = {
  id: CONVERSATION_ID,
  workspace_id: WORKSPACE_ID,
  title: "E2E Conversation",
  project_id: null,
  created_by: USER_ID,
  created_at: AT,
  updated_at: AT,
  version: 1,
};

const budget = {
  id: "55555555-5555-5555-5555-555555555555",
  workflow_type: null,
  limit_usd: "100.00",
  spent_usd: "10.00",
  remaining_usd: "90.00",
  period_started_at: AT,
  period_days: 30,
  breaker_open: false,
  breaker_reason: null,
};

const run = {
  id: "66666666-6666-6666-6666-666666666666",
  workspace_id: WORKSPACE_ID,
  workflow_type: "project_kickoff",
  definition_version: 1,
  status: "running",
  project_id: PROJECT_ID,
  detail: null,
  triggered_by: USER_ID,
  started_at: AT,
  finished_at: null,
  created_at: AT,
  steps: [],
};

/** Path pattern to payload. First match wins; order is therefore meaningful. */
const ROUTES = [
  [/^\/api\/v1\/auth\/me$/, () => profile],
  [/^\/api\/v1\/workspaces$/, () => [workspace]],
  [/^\/api\/v1\/workspaces\/[^/]+\/permissions$/, () => ({
    workspace_id: WORKSPACE_ID,
    role: "owner",
    permissions: ["workspace:read", "workspace:write"],
  })],
  [/^\/api\/v1\/workspaces\/[^/]+\/ai\/providers$/, () => []],
  [/^\/api\/v1\/workspaces\/[^/]+\/ai\/budgets$/, () => [budget]],
  [/^\/api\/v1\/workspaces\/[^/]+\/ai\/spend$/, () => []],
  [/^\/api\/v1\/workspaces\/[^/]+\/workflows\/runs$/, () => [run]],
  [/^\/api\/v1\/workspaces\/[^/]+\/projects$/, () => [project]],
  [/^\/api\/v1\/workspaces\/[^/]+\/projects\/[^/]+\/assets$/, () => []],
  [/^\/api\/v1\/workspaces\/[^/]+\/projects\/[^/]+$/, () => project],
  [/^\/api\/v1\/workspaces\/[^/]+\/chat\/conversations$/, () => [conversation]],
  [/^\/api\/v1\/workspaces\/[^/]+\/chat\/conversations\/[^/]+$/, () => ({
    conversation,
    messages: [],
  })],
];

function send(response, status, body) {
  const payload = JSON.stringify(body);
  response.writeHead(status, {
    "content-type": "application/json",
    "content-length": Buffer.byteLength(payload),
  });
  response.end(payload);
}

const server = createServer((request, response) => {
  const { pathname } = new URL(request.url ?? "/", `http://127.0.0.1:${PORT}`);

  // A readiness probe for Playwright's `webServer`, outside the API prefix so
  // it can never be mistaken for something the application calls.
  if (pathname === "/__ready") {
    return send(response, 200, { ready: true });
  }

  // The application must present the token it resolved. A stub that answered
  // anonymously would let an auth regression pass unnoticed, which is the one
  // thing this file must not do.
  if (!(request.headers.authorization ?? "").startsWith("Bearer ")) {
    return send(response, 401, { detail: "Not authenticated" });
  }

  for (const [pattern, payload] of ROUTES) {
    if (pattern.test(pathname)) {
      return send(response, 200, payload());
    }
  }

  return send(response, 404, { detail: `No stub route for ${pathname}` });
});

server.listen(PORT, "127.0.0.1", () => {
  process.stdout.write(`stub API listening on http://127.0.0.1:${PORT}\n`);
});
