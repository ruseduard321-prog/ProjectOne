/**
 * The server-side client for the ProjectOne API.
 *
 * **Server-only.** Every call here originates from a Next.js Server Component
 * or Route Handler, never from the browser. That is not a stylistic preference:
 * the access token lives in an httpOnly cookie the browser cannot read (see
 * `session.ts`), so a fetch issued from client code could not attach it. The
 * API also registers no CORS middleware, so a cross-origin browser request
 * would be refused before it reached a route.
 *
 * What crosses the network boundary is therefore browser → Next.js → API, and
 * this module is the second leg of it.
 *
 * Errors arrive in the STEP-12 envelope — `{"detail", "request_id"}` — and are
 * surfaced as {@link ApiError} rather than thrown as bare strings, so a caller
 * can render the message and the correlation id without re-parsing the body.
 *
 * The boundary is enforced by the callers rather than by a `server-only` import:
 * every module that imports this one also imports `next/headers`, which Next.js
 * refuses to bundle into client code. Adding a dependency to restate a
 * constraint the call graph already guarantees would be surface area for no
 * gain (CLAUDE.md §28).
 */

import { env } from "@/lib/env";

/** The error envelope every ProjectOne API failure carries (STEP-12). */
export interface ApiErrorBody {
  readonly detail: string;
  readonly request_id: string | null;
}

/**
 * A non-2xx response from the API, carrying the envelope's own message.
 *
 * The `detail` is rendered to users verbatim. That is safe by construction: the
 * API's error contract already guarantees these messages are user-facing and
 * leak neither credentials nor internal state (`app/core/errors.py`). Improving
 * on them client-side is what turns a deliberately generic sign-up rejection
 * into an account-enumeration oracle.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly requestId: string | null;

  constructor(status: number, detail: string, requestId: string | null) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.requestId = requestId;
  }
}

/**
 * Raised when the API cannot be reached at all.
 *
 * Distinct from {@link ApiError}: there is no status and no correlation id,
 * because no request was ever judged. Collapsing the two would tell a user
 * their password was wrong during an outage.
 */
export class ApiUnreachableError extends Error {
  constructor() {
    super("The service is temporarily unavailable. Please try again.");
    this.name = "ApiUnreachableError";
  }
}

/** Version prefix the API mounts every non-infrastructure route under. */
const API_PREFIX = "/api/v1";

function isErrorBody(value: unknown): value is ApiErrorBody {
  return (
    typeof value === "object" &&
    value !== null &&
    "detail" in value &&
    typeof (value as { detail: unknown }).detail === "string"
  );
}

interface ApiRequest {
  /** Path beneath the version prefix, e.g. `/auth/sign-in`. */
  readonly path: string;
  readonly method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  /** JSON body, serialized by this function. Omit for a bodyless request. */
  readonly body?: unknown;
  /** Access token to present as a bearer credential, when the route needs one. */
  readonly accessToken?: string;
  /**
   * The browser's address, forwarded so the API can rate limit public
   * endpoints per client rather than per proxy.
   *
   * Omitted for authenticated calls: those are limited by verified `user_id`
   * (ADR-002 §1), so an address would be collected for nothing — and the least
   * data that achieves the goal is the right amount (CLAUDE.md §16).
   */
  readonly clientAddress?: string;
}

/**
 * Call the ProjectOne API and decode its response.
 *
 * @throws {ApiError} On any non-2xx response, carrying the envelope's message
 *   and correlation id.
 * @throws {ApiUnreachableError} When the request never completed.
 */
export async function apiRequest<T>({
  path,
  method,
  body,
  accessToken,
  clientAddress,
}: ApiRequest): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };

  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  if (accessToken !== undefined) {
    headers.Authorization = `Bearer ${accessToken}`;
  }

  // Set, never appended to. This process is the first trusted hop, so whatever
  // a browser may have sent under this name is discarded rather than carried
  // forward — appending would splice an attacker-chosen value into a chain the
  // API is about to trust (ADR-002 §5).
  if (clientAddress !== undefined) {
    headers["X-Forwarded-For"] = clientAddress;
  }

  let response: Response;

  try {
    response = await fetch(`${env.apiUrl}${API_PREFIX}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      // Authentication responses are per-request by definition. Next.js caches
      // fetches aggressively by default, and a cached session response is a
      // credential served to the wrong person.
      cache: "no-store",
    });
  } catch {
    // Deliberately not logging the request: the body of a sign-in is a
    // password, and the backend's redacting filter (STEP-12) does not extend
    // to this process (CLAUDE.md §16).
    throw new ApiUnreachableError();
  }

  // A 204 carries no body, so parsing one is not a failure to tolerate — it is
  // the expected outcome. `.catch(() => null)` already handles it, and the null
  // is only ever returned to a caller whose response type says `void`.
  const payload: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    const detail = isErrorBody(payload) ? payload.detail : "The request could not be completed";
    const requestId =
      isErrorBody(payload) && typeof payload.request_id === "string" ? payload.request_id : null;

    throw new ApiError(response.status, detail, requestId);
  }

  return payload as T;
}

/** The session shape `POST /auth/sign-in` and `/auth/refresh` return. */
export interface ApiSession {
  readonly access_token: string;
  readonly refresh_token: string;
  readonly expires_in: number;
  readonly user_id: string;
  readonly email: string | null;
}

/** The outcome of `POST /auth/sign-up`. */
export interface ApiSignUpResult {
  readonly user_id: string | null;
  readonly email_confirmation_required: boolean;
  readonly session: ApiSession | null;
}

/** The caller's own profile, from `GET /auth/me`. */
export interface ApiProfile {
  readonly id: string;
  readonly email: string;
  readonly display_name: string | null;
}

export function signUp(
  email: string,
  password: string,
  clientAddress?: string,
): Promise<ApiSignUpResult> {
  return apiRequest<ApiSignUpResult>({
    path: "/auth/sign-up",
    method: "POST",
    body: { email, password },
    clientAddress,
  });
}

export function signIn(
  email: string,
  password: string,
  clientAddress?: string,
): Promise<ApiSession> {
  return apiRequest<ApiSession>({
    path: "/auth/sign-in",
    method: "POST",
    body: { email, password },
    clientAddress,
  });
}

export function signOut(accessToken: string): Promise<{ message: string }> {
  return apiRequest<{ message: string }>({
    path: "/auth/sign-out",
    method: "POST",
    accessToken,
  });
}

export function refreshSession(
  refreshToken: string,
  clientAddress?: string,
): Promise<ApiSession> {
  return apiRequest<ApiSession>({
    path: "/auth/refresh",
    method: "POST",
    body: { refresh_token: refreshToken },
    clientAddress,
  });
}

export function readProfile(accessToken: string): Promise<ApiProfile> {
  return apiRequest<ApiProfile>({
    path: "/auth/me",
    method: "GET",
    accessToken,
  });
}

export function updateProfile(accessToken: string, displayName: string): Promise<ApiProfile> {
  return apiRequest<ApiProfile>({
    path: "/auth/me",
    method: "PATCH",
    body: { display_name: displayName },
    accessToken,
  });
}

/** A workspace the caller belongs to, from `GET /workspaces`. */
export interface ApiWorkspace {
  readonly id: string;
  readonly name: string;
  readonly owner_id: string;
}

export function listWorkspaces(accessToken: string): Promise<ApiWorkspace[]> {
  return apiRequest<ApiWorkspace[]>({
    path: "/workspaces",
    method: "GET",
    accessToken,
  });
}

export function renameWorkspace(
  accessToken: string,
  workspaceId: string,
  name: string,
): Promise<ApiWorkspace> {
  return apiRequest<ApiWorkspace>({
    path: `/workspaces/${workspaceId}`,
    method: "PATCH",
    body: { name },
    accessToken,
  });
}

/** The caller's role in a workspace, from `GET /workspaces/{id}/permissions`. */
export interface ApiPermissions {
  readonly workspace_id: string;
  readonly role: "owner" | "admin" | "member";
  readonly permissions: readonly string[];
}

export function readPermissions(
  accessToken: string,
  workspaceId: string,
): Promise<ApiPermissions> {
  return apiRequest<ApiPermissions>({
    path: `/workspaces/${workspaceId}/permissions`,
    method: "GET",
    accessToken,
  });
}

/**
 * A stored provider key, as the settings screen may see it.
 *
 * **There is no field for the key itself, and there never will be.** The API
 * returns `last_four` and nothing more, because no route in the backend can
 * produce a stored key — see `app/routers/ai_settings.py`. A field added here
 * would have nothing to populate it from.
 */
export interface ApiProviderCredential {
  readonly id: string;
  readonly provider: string;
  readonly last_four: string;
}

export function listProviderCredentials(
  accessToken: string,
  workspaceId: string,
): Promise<ApiProviderCredential[]> {
  return apiRequest<ApiProviderCredential[]>({
    path: `/workspaces/${workspaceId}/ai/providers`,
    method: "GET",
    accessToken,
  });
}

export function storeProviderCredential(
  accessToken: string,
  workspaceId: string,
  provider: string,
  apiKey: string,
): Promise<ApiProviderCredential> {
  return apiRequest<ApiProviderCredential>({
    path: `/workspaces/${workspaceId}/ai/providers/${provider}`,
    method: "PUT",
    body: { api_key: apiKey },
    accessToken,
  });
}

export function revokeProviderCredential(
  accessToken: string,
  workspaceId: string,
  provider: string,
): Promise<void> {
  return apiRequest<void>({
    path: `/workspaces/${workspaceId}/ai/providers/${provider}`,
    method: "DELETE",
    accessToken,
  });
}

/**
 * A spend ceiling and its usage.
 *
 * Amounts are strings, matching the API. They are rendered and compared as
 * decimal strings rather than parsed to `number`: a ceiling that survives a
 * round trip through JavaScript's binary floating point is a ceiling that can be
 * displayed truthfully, and `0.1 + 0.2` is the reason not to find out otherwise.
 */
export interface ApiBudget {
  readonly id: string;
  readonly workflow_type: string | null;
  readonly limit_usd: string;
  readonly spent_usd: string;
  readonly remaining_usd: string;
  readonly period_started_at: string;
  readonly period_days: number;
  readonly breaker_open: boolean;
  readonly breaker_reason: string | null;
}

export function listBudgets(accessToken: string, workspaceId: string): Promise<ApiBudget[]> {
  return apiRequest<ApiBudget[]>({
    path: `/workspaces/${workspaceId}/ai/budgets`,
    method: "GET",
    accessToken,
  });
}

export function updateBudget(
  accessToken: string,
  workspaceId: string,
  limitUsd: string,
  periodDays?: number,
): Promise<ApiBudget> {
  return apiRequest<ApiBudget>({
    path: `/workspaces/${workspaceId}/ai/budgets`,
    method: "PUT",
    // `spent_usd` is deliberately absent and the API would answer 422 if it were
    // present — the running total is not a client-writable value.
    body: periodDays === undefined
      ? { limit_usd: limitUsd }
      : { limit_usd: limitUsd, period_days: periodDays },
    accessToken,
  });
}

/**
 * A project's position in its lifecycle.
 *
 * The values match the API's `ProjectStatus` and the database's
 * `ck_projects_status_valid` check constraint. A union rather than a string so a
 * typo in a component is a compile error rather than a status that silently
 * never matches.
 *
 * **The order of transitions is deliberately not encoded here.** Which moves are
 * legal comes from the server, per project, in `legal_transitions` — see
 * [[Project Lifecycle]]. A second copy of the state machine in TypeScript is
 * exactly what STEP-21 was told not to build, because two copies diverge.
 */
export type ApiProjectStatus =
  | "idea"
  | "planning"
  | "generation"
  | "review"
  | "editing"
  | "approval"
  | "publishing"
  | "analytics"
  | "archive";

/** One project, from `GET /workspaces/{id}/projects`. */
export interface ApiProject {
  readonly id: string;
  readonly workspace_id: string;
  readonly name: string;
  readonly description: string | null;
  readonly status: ApiProjectStatus;
  /**
   * Every state this project can move to in one step, decided by the server.
   *
   * Rendered directly as the available actions. Empty for an archived project,
   * which is the terminal state saying so.
   */
  readonly legal_transitions: readonly ApiProjectStatus[];
  readonly created_by: string;
  readonly created_at: string;
  readonly updated_at: string;
  readonly version: number;
}

/**
 * What an asset is.
 *
 * A closed vocabulary, matching the API's `AssetKind` and the database's
 * `ck_assets_kind_valid`. Not free text: the constraint refuses anything else,
 * so a client offering an arbitrary string would be offering a request that
 * cannot succeed.
 */
export type ApiAssetKind = "document" | "image" | "video" | "audio";

/** One asset attached to a project. */
export interface ApiAsset {
  readonly id: string;
  readonly project_id: string;
  readonly name: string;
  readonly kind: ApiAssetKind;
  /** Always null today — no storage backend exists. See `app/schemas/project.py`. */
  readonly storage_path: string | null;
  readonly created_by: string;
  readonly created_at: string;
}

export function listProjects(accessToken: string, workspaceId: string): Promise<ApiProject[]> {
  return apiRequest<ApiProject[]>({
    path: `/workspaces/${workspaceId}/projects`,
    method: "GET",
    accessToken,
  });
}

export function readProject(
  accessToken: string,
  workspaceId: string,
  projectId: string,
): Promise<ApiProject> {
  return apiRequest<ApiProject>({
    path: `/workspaces/${workspaceId}/projects/${projectId}`,
    method: "GET",
    accessToken,
  });
}

export function createProject(
  accessToken: string,
  workspaceId: string,
  name: string,
  description?: string,
): Promise<ApiProject> {
  return apiRequest<ApiProject>({
    path: `/workspaces/${workspaceId}/projects`,
    method: "POST",
    // `status` is deliberately absent — a project always starts in `idea`, and
    // the API would answer 422 for an unexpected field.
    body: description === undefined ? { name } : { name, description },
    accessToken,
  });
}

export function renameProject(
  accessToken: string,
  workspaceId: string,
  projectId: string,
  name: string,
  description: string | null,
): Promise<ApiProject> {
  return apiRequest<ApiProject>({
    path: `/workspaces/${workspaceId}/projects/${projectId}`,
    method: "PATCH",
    body: { name, description },
    accessToken,
  });
}

/**
 * Move a project to a new lifecycle state.
 *
 * A refused move answers 409 and surfaces as an {@link ApiError}. The UI offers
 * only `legal_transitions`, so a 409 here means the project changed underneath
 * the page — which is worth reporting rather than hiding.
 */
export function transitionProject(
  accessToken: string,
  workspaceId: string,
  projectId: string,
  status: ApiProjectStatus,
): Promise<ApiProject> {
  return apiRequest<ApiProject>({
    path: `/workspaces/${workspaceId}/projects/${projectId}/transitions`,
    method: "POST",
    body: { status },
    accessToken,
  });
}

export function deleteProject(
  accessToken: string,
  workspaceId: string,
  projectId: string,
): Promise<void> {
  return apiRequest<void>({
    path: `/workspaces/${workspaceId}/projects/${projectId}`,
    method: "DELETE",
    accessToken,
  });
}

export function listAssets(
  accessToken: string,
  workspaceId: string,
  projectId: string,
): Promise<ApiAsset[]> {
  return apiRequest<ApiAsset[]>({
    path: `/workspaces/${workspaceId}/projects/${projectId}/assets`,
    method: "GET",
    accessToken,
  });
}

export function createAsset(
  accessToken: string,
  workspaceId: string,
  projectId: string,
  name: string,
  kind: ApiAssetKind,
): Promise<ApiAsset> {
  return apiRequest<ApiAsset>({
    path: `/workspaces/${workspaceId}/projects/${projectId}/assets`,
    method: "POST",
    body: { name, kind },
    accessToken,
  });
}

export function deleteAsset(
  accessToken: string,
  workspaceId: string,
  projectId: string,
  assetId: string,
): Promise<void> {
  return apiRequest<void>({
    path: `/workspaces/${workspaceId}/projects/${projectId}/assets/${assetId}`,
    method: "DELETE",
    accessToken,
  });
}

/** One entry from a workspace's AI spend history. */
export interface ApiSpendRecord {
  readonly created_at: string;
  readonly provider: string;
  readonly model: string;
  readonly workflow_type: string;
  readonly prompt_tokens: number;
  readonly completion_tokens: number;
  readonly cost_usd: string;
}

export function listSpendRecords(
  accessToken: string,
  workspaceId: string,
): Promise<ApiSpendRecord[]> {
  return apiRequest<ApiSpendRecord[]>({
    path: `/workspaces/${workspaceId}/ai/spend`,
    method: "GET",
    accessToken,
  });
}

/**
 * Who authored a stored message.
 *
 * Two values, mirroring `MessageRole` in `app/schemas/chat.py` and the database's
 * `ck_messages_role_valid`. `system` is absent here for the same reason it is
 * absent there: a system instruction is assembled at call time and never stored,
 * so it can never arrive in a response.
 */
export type ApiMessageRole = "user" | "assistant";

/** One stored message in a conversation. */
export interface ApiChatMessage {
  readonly id: string;
  readonly conversation_id: string;
  readonly role: ApiMessageRole;
  readonly content: string;
  /**
   * Which provider and model produced this, when one did.
   *
   * Null on a user message, which no provider produced. Carried so a reply
   * served after a fallback can be attributed to the provider that actually
   * answered rather than the one the workspace configured (CLAUDE.md §15).
   */
  readonly provider: string | null;
  readonly model: string | null;
  readonly token_count: number;
  readonly created_at: string;
}

/** One conversation, without its messages. */
export interface ApiConversation {
  readonly id: string;
  readonly workspace_id: string;
  readonly title: string;
  readonly project_id: string | null;
  readonly created_by: string;
  readonly created_at: string;
  readonly updated_at: string;
  readonly version: number;
}

/** One conversation together with its full transcript. */
export interface ApiConversationDetail {
  readonly conversation: ApiConversation;
  readonly messages: readonly ApiChatMessage[];
}

/** The outcome of one completed exchange. */
export interface ApiTurn {
  readonly conversation: ApiConversation;
  readonly user_message: ApiChatMessage;
  readonly assistant_message: ApiChatMessage;
}

export function listConversations(
  accessToken: string,
  workspaceId: string,
): Promise<ApiConversation[]> {
  return apiRequest<ApiConversation[]>({
    path: `/workspaces/${workspaceId}/chat/conversations`,
    method: "GET",
    accessToken,
  });
}

export function readConversation(
  accessToken: string,
  workspaceId: string,
  conversationId: string,
): Promise<ApiConversationDetail> {
  return apiRequest<ApiConversationDetail>({
    path: `/workspaces/${workspaceId}/chat/conversations/${conversationId}`,
    method: "GET",
    accessToken,
  });
}

/**
 * Send one message and receive the reply.
 *
 * Omitting `conversationId` starts a new conversation, which is why the returned
 * turn carries the conversation: it is the only place a caller learns the id of
 * one that was just created.
 *
 * This is the only call here that reaches a provider, so it is the only one that
 * can fail with a governance refusal (402/503) or a provider error (502/503).
 * Those are rendered as messages, never as a fabricated reply.
 */
export function sendChatMessage(
  accessToken: string,
  workspaceId: string,
  content: string,
  conversationId?: string,
  projectId?: string,
): Promise<ApiTurn> {
  return apiRequest<ApiTurn>({
    path: `/workspaces/${workspaceId}/chat/messages`,
    method: "POST",
    // Optional ids are omitted rather than sent as null: the request model
    // forbids extra fields, and an explicit null would say the same thing less
    // clearly.
    //
    // `conversationId` may name a conversation that does not exist yet — the
    // API creates one with that id. That is what lets a caller know the id
    // before the call, so a failed first turn is still reachable and a retry
    // continues it rather than starting a second. See `sendMessageAction`.
    body: {
      content,
      ...(conversationId === undefined ? {} : { conversation_id: conversationId }),
      ...(projectId === undefined ? {} : { project_id: projectId }),
    },
    accessToken,
  });
}

export function deleteConversation(
  accessToken: string,
  workspaceId: string,
  conversationId: string,
): Promise<void> {
  return apiRequest<void>({
    path: `/workspaces/${workspaceId}/chat/conversations/${conversationId}`,
    method: "DELETE",
    accessToken,
  });
}
