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
  readonly method: "GET" | "POST";
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
