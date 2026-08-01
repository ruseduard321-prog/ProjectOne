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
| `LastOwnerError`       | 409    | Permission held; workspace state refuses.   |
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

from app.core.api import current_request_id
from app.core.logging import get_logger, log_context
from app.core.security import (
    AuthError,
    AuthorizationError,
    IdentityProviderError,
    LastOwnerError,
)

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
    (LastOwnerError, _last_owner_conflict),
    (RequestValidationError, _validation_failed),
    (HTTPException, _http_exception),
    (Exception, _unhandled),
)
