"""The project-wide error contract, and the handlers that apply it.

Every failure leaves the API through this module. Translation lives here rather
than in routers because a mapping that depends on each router remembering to
catch an exception is a mapping that eventually surfaces as a 500 — a service
can raise without the route above it knowing (CLAUDE.md §12, §24).

## The envelope

    {"detail": "<a message safe to show a user>", "request_id": "<correlation id>"}

`detail` is FastAPI's own field name, kept rather than replaced. Every
`HTTPException`, and every 422 the framework generates from a schema, already
produces it; inventing a different key would mean re-rendering validation
errors to fight the framework for no gain, and would break every existing
client and test for a cosmetic difference.

`request_id` is added alongside it, never nested inside it, and that placement
is load-bearing. Two response-body properties inherited from STEP-10 and
STEP-11 must survive this step:

- Every **authentication** failure returns an identical `detail`, whichever
  cause — expired, forged, or absent. Distinguishing them is a free oracle.
- Every **authorization** refusal returns an identical `detail`, whether the
  caller's role was insufficient or they were not a member at all. The second
  is what stops a workspace id becoming an existence oracle.

`request_id` necessarily varies per request, so it cannot live inside the
compared value. Tests assert on `detail`; the id sits beside it, which is what
makes a user-reported failure findable without weakening either property.

## The status codes

| Exception              | Status | Why                                         |
|------------------------|--------|---------------------------------------------|
| `AuthError`            | 401    | Identity is unknown or unverifiable.        |
| `IdentityProviderError`| 503    | Ours, not the caller's — see below.         |
| `AuthorizationError`   | 403    | Identity is known; the answer is still no.  |
| `ProjectNotFoundError` | 404    | No such resource, or RLS hid it — one answer.|
| `RunNotFoundError`     | 404    | The same, for a workflow run.               |
| `LastOwnerError`       | 409    | Permission held; workspace state refuses.   |
| `IllegalTransitionError`| 409   | Permission held; resource state refuses.    |
| `RunNotResumableError` | 409    | The same, for a run's own state.            |
| `WorkflowError`        | 422    | The run could never have formed — see below.|
| Validation             | 422    | The request never formed a valid operation. |

The 401/403 split is deliberate and must not be collapsed: `AuthorizationError`
is not an `AuthError` subclass precisely so that a permission failure cannot be
mistaken for a credential failure, which would send a correct client into a
token-refresh loop over a settled "no" (see `app.core.security`).
"""

from collections.abc import Mapping
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# `app.core` importing `app.ai` is worth a word, because the name suggests the
# opposite direction. This module is not a general-purpose core utility -- it is
# the application's *error contract*, whose whole job is knowing every error type
# the application can raise and what HTTP answer each deserves. It already
# imports `app.core.security`'s hierarchy for the same reason.
#
# `app.ai.governance` imports only `app.ai.errors` and `app.core.logging`, so
# there is no cycle; verified by importing `app.main`. The alternative -- a
# local import inside the handler, as `app.core.config` uses for `parse_encryption_key`
# -- was rejected here: config genuinely is a lower layer that must not know
# about AI, whereas an error contract that does not name an error it must
# translate is an error contract with a hole in it.
from app.ai.errors import NoProviderAvailableError, ProviderError
from app.ai.governance import AIShutdownError, GovernanceError, SpendBreakerOpenError
from app.core.api import current_request_id
from app.core.logging import get_logger, log_context
from app.core.security import (
    AuthError,
    AuthorizationError,
    IdentityProviderError,
    LastOwnerError,
    RateLimitExceededError,
)

# The same reasoning as the `app.ai.governance` import above, and it applies
# unchanged: this module is the application's error *contract*, so it must name
# every error type the application can raise. `app.services.project_service`
# imports only `app.core.logging` and `app.repositories.projects`, so there is
# no cycle -- asserted by `test_no_import_cycle_reaches_the_error_contract`
# rather than left to be discovered at startup.
from app.services.asset_content import AssetContentError
from app.services.asset_storage_service import AssetFileNotFoundError
from app.services.chat_service import ConversationNotFoundError, TurnNotClaimableError
from app.services.project_service import IllegalTransitionError, ProjectNotFoundError
from app.storage.errors import (
    ObjectNotFoundError,
    StorageAccessDeniedError,
    StorageError,
    StorageUnavailableError,
)
from app.workflows.models import RunNotFoundError, RunNotResumableError, WorkflowError

logger = get_logger(__name__)


def error_body(detail: str) -> dict[str, Any]:
    """Build the standard error envelope.

    One function so the shape cannot drift between handlers — the failure mode
    being avoided is six near-identical dict literals that stop matching after
    someone edits five of them.
    """
    return {"detail": detail, "request_id": current_request_id()}


def error_response(
    status_code: int,
    detail: str,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """Build an error response carrying the standard envelope."""
    return JSONResponse(
        status_code=status_code,
        content=error_body(detail),
        headers=headers,
    )


def _authentication_failed(_request: Request, exception: Exception) -> JSONResponse:
    """Translate an authentication failure into 401, or 503 when it is ours.

    `IdentityProviderError` is a 503 because the caller's credentials were
    never actually judged: Supabase was unreachable. Returning 401 there tells
    a user their password is wrong during an outage, and hides the outage in
    the one metric that should reveal it.

    Every other cause returns 401 with an **identical** body. `str(exception)`
    — which says whether the token expired, failed its signature, or carried
    the wrong issuer — goes to the log, where it is a debugging aid rather than
    an oracle (CLAUDE.md §24).
    """
    logger.warning(log_context(event="authentication_failed", cause=type(exception).__name__))

    message = getattr(exception, "public_message", AuthError.public_message)

    if isinstance(exception, IdentityProviderError):
        return error_response(status.HTTP_503_SERVICE_UNAVAILABLE, message)

    return error_response(
        status.HTTP_401_UNAUTHORIZED,
        message,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _authorization_denied(_request: Request, exception: Exception) -> JSONResponse:
    """Translate a refused permission into a 403.

    Registered once rather than repeated as a `try/except` in every route that
    can raise it. A service may enforce a permission without the route knowing
    (see `DataOwnershipService`), and a check whose HTTP mapping depends on each
    router remembering to catch it is a check that eventually surfaces as a 500.

    403, not 401: the caller authenticated successfully and the answer is still
    no. `public_message` names neither the caller's role nor the permission
    required — that detail is a map of the permission model, and belongs in the
    log (CLAUDE.md §24).
    """
    logger.warning(log_context(event="authorization_denied", cause=type(exception).__name__))

    # Starlette types every handler as taking `Exception`, so the narrowing is
    # done here rather than in the signature. It cannot fail in practice --
    # FastAPI only routes the class this is registered against — but falling
    # back to the base message keeps a mis-registration a correct 403 rather
    # than an AttributeError inside the error handler.
    message = getattr(exception, "public_message", AuthorizationError.public_message)

    return error_response(status.HTTP_403_FORBIDDEN, message)


def _last_owner_conflict(_request: Request, exception: Exception) -> JSONResponse:
    """Translate the last-owner rule into a 409.

    **409, not 403.** The caller holds every permission the action requires --
    an owner leaving their own workspace has `LEAVE_WORKSPACE`. What refuses
    them is the workspace's state, and no amount of re-authenticating or
    role-changing would help. A 403 here would send an owner looking for a
    permission problem that does not exist.

    Unlike the authorization messages, this body is deliberately specific: it
    names transferring ownership as the remedy. It leaks nothing an owner does
    not already know, and withholding it would leave them stuck.
    """
    message = getattr(exception, "public_message", "Conflict")

    return error_response(status.HTTP_409_CONFLICT, message)


def _resource_not_found(_request: Request, exception: Exception) -> JSONResponse:
    """Translate a missing project or asset into a 404.

    **404, and deliberately the same 404 for "absent" and "hidden by RLS".**
    `ProjectNotFoundError` conflates the two at the point it is raised
    (`app.services.project_service`), so there is nothing here to distinguish
    even if this handler wanted to -- which is the property that stops a project
    id becoming an existence oracle across tenants.

    Worth reading against `_authorization_denied`, because the two look
    inconsistent and are not. A **workspace** id answers 403 whether the caller
    is a non-member or merely under-privileged, because the caller supplied that
    id as the thing they claim access to and 404 there would confirm which
    workspace ids exist. A **project** id inside a workspace the caller does
    belong to answers 404, because from the caller's side an invisible project
    and an absent one are the same fact, and the workspace-level check has
    already refused anyone who does not belong.

    The rule underneath both: **one answer per question, regardless of cause.**
    """
    message = getattr(exception, "public_message", "Not found")

    return error_response(status.HTTP_404_NOT_FOUND, message)


def _asset_content_refused(_request: Request, exception: Exception) -> JSONResponse:
    """Translate a refused upload into the status its rule deserves.

    **One handler, several statuses**, read from the exception rather than
    branched on its type. `AssetContentError` carries `status_code` precisely so
    a new refusal rule is one class in `app.services.asset_content` instead of a
    class plus an entry here plus a branch -- three places to keep in step for a
    body that is identical apart from a number.

    The statuses each say something a caller can act on:

    - **413** the file is too big. Sending it again will not help; a smaller one
      will.
    - **415** the type is not supported, the extension disagrees with it, or the
      bytes disagree with both. All three mean "this media is not acceptable",
      which is what 415 says.
    - **400** the upload was empty. Not 415: there is no media to find fault
      with, the request is simply malformed.

    422 would be wrong for all of them. The request *did* form a valid
    operation -- it was well-shaped, authorized, and understood. What refuses it
    is the content, which is a different question from whether the request
    parsed.
    """
    message = getattr(exception, "public_message", "The uploaded file was refused.")
    code = getattr(exception, "status_code", status.HTTP_400_BAD_REQUEST)

    return error_response(code, message)


def _storage_failed(_request: Request, exception: Exception) -> JSONResponse:
    """Translate a storage backend failure into a status that tells the truth.

    Registered against the **base** `StorageError`, so a subclass added later in
    `app.storage.errors` is answered the moment it is raised rather than falling
    through to `_unhandled` as a 500 -- the same reasoning `ProviderError` uses.

    Three answers, split by what the caller can do:

    - **404** the object does not exist. Reported identically to a missing asset
      row, because from the caller's side "no such file" is one fact.
    - **403** the operation was refused. In practice this means an object outside
      the calling workspace's namespace, which ProjectOne refuses before the
      backend is asked -- a security-relevant event, and never a 404 that would
      hint the object exists elsewhere.
    - **503** the backend failed or was unreachable. **Ours, not the caller's**,
      so it must not be a 4xx: a client that retries later is doing the right
      thing, and a 4xx would tell them to change a request that was correct.

    The message is the error's `public_message` throughout, which is why no
    bucket name, object key or credential can reach a response body from here
    (CLAUDE.md §16, §24).
    """
    if isinstance(exception, ObjectNotFoundError):
        code = status.HTTP_404_NOT_FOUND
    elif isinstance(exception, StorageAccessDeniedError):
        code = status.HTTP_403_FORBIDDEN
    elif isinstance(exception, StorageUnavailableError):
        code = status.HTTP_503_SERVICE_UNAVAILABLE
    else:
        # The base class raised directly, which its docstring says never happens.
        # Answered as an outage rather than a caller error: an unclassified
        # storage failure is far more likely to be ours than theirs.
        code = status.HTTP_503_SERVICE_UNAVAILABLE

    logger.warning(
        log_context(
            event="storage_operation_failed",
            error=type(exception).__name__,
            status_code=code,
        )
    )

    return error_response(code, getattr(exception, "public_message", "Storage request failed."))


def _illegal_transition(_request: Request, exception: Exception) -> JSONResponse:
    """Translate a refused lifecycle move into a 409.

    **409, not 422.** The request was well-formed and the status was in the
    vocabulary -- `ProjectTransitionRequest` typed it as `ProjectStatus`, so
    anything outside the vocabulary was already a 422 before this could be
    reached. What refuses the caller is the *current state of the resource*,
    which is precisely what 409 means, and it is the same distinction
    `LastOwnerError` draws: permission held, state says no.

    422 here would send a client checking their serialization for a problem that
    does not exist. 403 would send them to the permission model, which is also
    not it.

    The message names both states, unlike the authorization and authentication
    messages. That is safe and useful: the caller already knows the current
    status -- they read the project to attempt this -- and telling them why the
    move was refused is the difference between an actionable error and a mystery
    (CLAUDE.md §24).
    """
    message = getattr(exception, "public_message", "Conflict")

    return error_response(status.HTTP_409_CONFLICT, message)


def _workflow_refused(_request: Request, exception: Exception) -> JSONResponse:
    """Translate a workflow's own refusal into a 422.

    **422, and only for the base `WorkflowError`.** Its two subclasses have their
    own entries in the table below and are matched first, because Starlette
    dispatches on the most specific registered class -- `RunNotFoundError` is a
    404 and `RunNotResumableError` a 409, and inheriting this handler would
    collapse both into 422.

    What reaches here is the case where **the run could never have formed**: an
    unknown workflow type, a run started against a definition that no longer has
    the step it stopped at, a workflow requiring a project that was not given
    one. Each is the request failing to describe a valid operation, which is what
    422 means -- as opposed to 409, where the request is valid and the resource's
    state refuses it.

    A step *failing mid-run* never reaches here at all. That is not an HTTP
    error: the run was started successfully and the response is a run in
    `failed`, with the reason on the row. Reporting a failed run as a failed
    request would tell a client its call did not happen when it did.
    """
    message = getattr(exception, "public_message", WorkflowError.public_message)

    return error_response(status.HTTP_422_UNPROCESSABLE_CONTENT, message)


def _rate_limit_exceeded(_request: Request, exception: Exception) -> JSONResponse:
    """Translate a per-user rate limit refusal into a 429.

    **429, not 401 and not 403.** The credentials are valid and the permissions
    sufficient; only the request rate is not. A 401 would send a correct client
    into a token-refresh loop over a condition refreshing cannot fix, and a 403
    would tell them to change a role that is already right.

    The response is deliberately identical in shape to the one
    `RateLimitMiddleware` returns -- same status, same message, same
    `Retry-After`. The middleware answers directly because it runs outside the
    handler chain by definition; this one goes through the table because it can.
    A caller must not be able to tell the two apart: a difference would reveal
    whether the endpoint considered them authenticated, which is information a
    refusal must not carry.
    """
    retry_after = getattr(exception, "retry_after_seconds", 60)
    message = getattr(exception, "public_message", RateLimitExceededError.public_message)

    return error_response(
        status.HTTP_429_TOO_MANY_REQUESTS,
        message,
        headers={"Retry-After": str(retry_after)},
    )


def _http_exception(_request: Request, exception: Exception) -> JSONResponse:
    """Render a raised `HTTPException` into the standard envelope.

    FastAPI's default handler emits `{"detail": ...}` without the correlation
    id. Overriding it is what makes "every error body carries a request id"
    true of *every* error rather than only the ones with a bespoke handler —
    including the 404s Starlette raises for an unmatched route.
    """
    if not isinstance(exception, HTTPException):  # pragma: no cover - defensive
        return error_response(status.HTTP_500_INTERNAL_SERVER_ERROR, "Internal server error")

    detail = exception.detail if isinstance(exception.detail, str) else "Request failed"

    return error_response(exception.status_code, detail, headers=exception.headers)


def _validation_failed(_request: Request, exception: Exception) -> JSONResponse:
    """Render a schema validation failure into the standard envelope.

    422, and the field-level errors are kept: unlike an authentication or
    authorization message, telling a caller that `email` is malformed reveals
    nothing they did not just send. Withholding it would make every client
    integration a guessing game.

    The `input` value pydantic echoes back is stripped, deliberately — on
    `/auth/sign-up` it is the submitted password, and reflecting a credential
    into a response body is how it ends up in a browser console, an error
    tracker, and a support ticket.
    """
    errors: list[dict[str, Any]] = []

    if isinstance(exception, RequestValidationError):
        for error in exception.errors():
            errors.append(
                {
                    "field": ".".join(str(part) for part in error.get("loc", ())),
                    "message": error.get("msg", "Invalid value"),
                    "type": error.get("type", "value_error"),
                }
            )

    body = error_body("The request could not be validated")
    body["errors"] = errors

    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content=body)


def _unhandled(_request: Request, exception: Exception) -> JSONResponse:
    """Return a 500 without telling the caller what broke.

    The traceback goes to the log with the correlation id attached; the caller
    gets a fixed message and that id. An exception message rendered into a
    response body is how a stack trace, a query fragment or a connection string
    reaches a user (CLAUDE.md §24).
    """
    logger.exception(log_context(event="unhandled_exception", cause=type(exception).__name__))

    return error_response(status.HTTP_500_INTERNAL_SERVER_ERROR, "Internal server error")


def _governance_refusal(_request: Request, exception: Exception) -> JSONResponse:
    """Translate a cost-governance refusal into 402 or 503.

    Registered by [[STEP-18 AI Cost Governance Controls]], before any route can
    raise one. Without an entry here a budget refusal would reach the client as
    a **500** -- a deliberate, correct control reported as a server crash, which
    would send a user to support and an engineer to a stack trace that does not
    exist.

    Two statuses, because the two refusals are genuinely different answers:

    - **402 Payment Required** for a budget ceiling. The request was well-formed
      and authorized, and the workspace has spent its allowance. It succeeds
      again next period, or once the limit is raised -- which is what 402 means
      more precisely than any 4xx alternative. 403 would say "you may never do
      this", which is wrong and sends the reader to the permission model.
    - **503 Service Unavailable** for a shutdown or a tripped breaker. Nothing
      about the caller is at fault, and the condition is operational and
      temporary -- the same reasoning that makes `IdentityProviderError` a 503
      rather than a 401.

    `ExecutionLimitExceededError` is a 400-class refusal of the *run* rather than
    a spend condition, but it is deliberately answered as 402 alongside the
    budget: from the caller's side both mean "this workflow consumed its
    allowance", and splitting them would leak how ProjectOne bounds runs.

    Retryable governance refusals carry `Retry-After`, like the rate limiter's
    429 -- a client told to back off without being told how long backs off
    arbitrarily.
    """
    logger.warning(log_context(event="ai_governance_refusal", cause=type(exception).__name__))

    message = getattr(exception, "public_message", GovernanceError.public_message)

    if isinstance(exception, AIShutdownError | SpendBreakerOpenError):
        return error_response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            message,
            headers={"Retry-After": str(_GOVERNANCE_RETRY_AFTER_SECONDS)},
        )

    return error_response(status.HTTP_402_PAYMENT_REQUIRED, message)


def _provider_failed(_request: Request, exception: Exception) -> JSONResponse:
    """Translate an AI provider failure into an honest status.

    **This handler exists because [[STEP-23 AI Chat End to End]] is the first
    place a provider failure reaches a user.** Until chat, the only caller was
    the workflow engine, which records a failure in the run's own status column
    and returns 201 -- so a `ProviderError` never reached HTTP and had no
    handler. Without one it would have surfaced as a 500: a correct, deliberate
    failure reported as a bug in ProjectOne. That is the same shape as the
    STEP-18 defect where a governance refusal reached the client as a 500.

    The split:

    - **`NoProviderAvailableError` is 503**, because nothing was attempted. It
      usually means the workspace has configured no key, which is a
      configuration state that will keep answering identically until someone
      changes it -- so it carries `Retry-After` like the governance refusals.
    - **Everything else is 502.** The request was well-formed and ProjectOne did
      its part; an upstream ProjectOne depends on is what failed. 500 would
      claim the bug is here, and 400 would blame a caller who did nothing wrong.

    The message is the exception's own `public_message`, never its internal
    detail: vendor error text can quote request content back, and request
    content is the user's prompt (CLAUDE.md §24).
    """
    logger.warning(
        log_context(
            event="ai_provider_failure",
            cause=type(exception).__name__,
            provider=getattr(exception, "provider", None),
        )
    )

    message = getattr(exception, "public_message", ProviderError.public_message)

    if isinstance(exception, NoProviderAvailableError):
        return error_response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            message,
            headers={"Retry-After": str(_GOVERNANCE_RETRY_AFTER_SECONDS)},
        )

    return error_response(status.HTTP_502_BAD_GATEWAY, message)


#: What a client is told to wait before retrying a shutdown or breaker refusal.
#:
#: Deliberately long. Neither condition clears on its own: a shutdown is lifted
#: by an operator and a spend breaker is reset manually, so a short value would
#: invite a client to hammer an endpoint that will refuse it identically for as
#: long as the incident lasts.
_GOVERNANCE_RETRY_AFTER_SECONDS = 300


#: Every handler the application registers, in one table.
#:
#: A table rather than a sequence of `add_exception_handler` calls in the
#: factory, so the full error contract is readable in one place and adding a
#: new error type is one line next to its peers.
#:
#: Order is irrelevant to Starlette — it dispatches on the most specific
#: registered class — but `WorkspaceAccessError` deliberately has no entry: it
#: subclasses `AuthorizationError` and must be answered identically, which
#: inheriting the handler guarantees more reliably than a duplicate entry would.
EXCEPTION_HANDLERS: tuple[tuple[type[Exception] | int, Any], ...] = (
    (AuthError, _authentication_failed),
    (AuthorizationError, _authorization_denied),
    (ProjectNotFoundError, _resource_not_found),
    # An asset with no bytes is the same answer as an asset that is not there:
    # 404, through the handler that already says so. Kept as its own type at the
    # raise site so the service can log the difference, which is worth counting
    # -- it is the visible residue of a failed upload (STEP-28 Task 5).
    (AssetFileNotFoundError, _resource_not_found),
    (IllegalTransitionError, _illegal_transition),
    # Registered as base classes, like `ProviderError` below: every refusal in
    # each hierarchy is answered by the branch inside its handler, so a rule or
    # a backend failure added later is covered when it is raised rather than
    # falling through to `_unhandled` as a 500.
    (AssetContentError, _asset_content_refused),
    (StorageError, _storage_failed),
    # The two subclasses are registered alongside their base and **before** it in
    # reading order, though Starlette's most-specific-match makes the order
    # irrelevant to dispatch. Both reuse the handlers their semantics already
    # match exactly: a run that is absent-or-hidden is the same answer as a
    # project that is, and a run refusing an action because of its own state is
    # the same answer as an illegal project transition. Writing a third and
    # fourth handler that produced identical responses would be two more places
    # for the contract to drift.
    (RunNotFoundError, _resource_not_found),
    (RunNotResumableError, _illegal_transition),
    (WorkflowError, _workflow_refused),
    (LastOwnerError, _last_owner_conflict),
    (RateLimitExceededError, _rate_limit_exceeded),
    (GovernanceError, _governance_refusal),
    # A conversation that is absent or hidden is the same answer as a project
    # that is -- reusing the handler rather than writing a third that returns an
    # identical body, for the reason the workflow entries above give.
    (ConversationNotFoundError, _resource_not_found),
    # 409, matching the last-owner rule rather than 403 or 500: the caller holds
    # every permission this needs, and what refuses them is the turn's *state*.
    # A turn already being answered -- or one left claimed by a process that
    # died mid-call -- is a conflict, and re-authenticating would not help.
    (TurnNotClaimableError, _last_owner_conflict),
    # Registered as the base class: every provider failure is answered by the
    # branch inside the handler, so a new subclass in `app.ai.errors` is covered
    # the moment it is raised rather than falling through to `_unhandled`.
    (ProviderError, _provider_failed),
    (RequestValidationError, _validation_failed),
    (HTTPException, _http_exception),
    (Exception, _unhandled),
)
