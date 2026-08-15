"""Authentication router.

Validates input, calls the service, returns a response — nothing else
(CLAUDE.md §12).

**No error translation happens here.** `AuthError` and its subclasses are
mapped to status codes by the handlers in `app.core.errors`, registered once
for the whole application. This router previously owned that mapping in a
`_reject` helper; STEP-12 moved it, because a mapping that each router must
remember to apply is a mapping that a future router silently omits — and an
uncaught `AuthError` is a 500 where a 401 was meant.

The one exception below is deliberate and is not a translation: sign-up turns a
rejected registration into a 400 with a *different, generic* message, which is
a decision about this endpoint rather than about the error type.
"""

import uuid

from fastapi import APIRouter, HTTPException, status

from app.core.api import current_request_id
from app.core.dependencies import (
    AccessTokenDep,
    AuthServiceDep,
    CurrentUserDep,
    SecurityEventServiceDep,
    TenantConnectionDep,
)
from app.core.security import CredentialsRejectedError
from app.repositories.supabase_auth import AuthSession
from app.schemas.auth import (
    MessageResponse,
    ProfileResponse,
    RefreshRequest,
    SessionResponse,
    SignInRequest,
    SignUpRequest,
    SignUpResponse,
)
from app.schemas.settings import ProfileUpdateRequest
from app.services.auth_service import AuthService
from app.services.security_event_service import (
    SecurityEventOutcome,
    SecurityEventReason,
    SecurityEventService,
    SecurityEventType,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _record_success(
    events: SecurityEventService,
    event_type: SecurityEventType,
    user_id: uuid.UUID | None = None,
) -> None:
    """Record a successful authentication event.

    A user id may be attached here and only here: the caller has already proved
    the account exists by authenticating against it, so the row discloses
    nothing they did not just demonstrate.
    """
    events.record(
        event_type,
        SecurityEventOutcome.SUCCEEDED,
        request_id=current_request_id(),
        user_id=user_id,
    )


def _record_failure(events: SecurityEventService, event_type: SecurityEventType) -> None:
    """Record a failed authentication attempt, anonymously.

    **No identity is passed, and none can be.** `record_failure` has no
    parameter for one — see `SecurityEventService`. The reason is the
    allowlisted token rather than the provider's message, which distinguishes
    cases the public response deliberately does not.
    """
    events.record_failure(
        event_type,
        request_id=current_request_id(),
        reason=SecurityEventReason.INVALID_CREDENTIALS,
    )


def _to_response(session: AuthSession) -> SessionResponse:
    """Convert a service-layer session into its response shape."""
    return SessionResponse(
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        expires_in=session.expires_in,
        user_id=session.user_id,
        email=session.email,
    )


@router.post(
    "/sign-up",
    response_model=SignUpResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new account",
)
def sign_up(
    request: SignUpRequest,
    auth_service: AuthServiceDep,
    events: SecurityEventServiceDep,
) -> SignUpResponse:
    """Register an identity and provision its ProjectOne profile.

    Returns 201 with a session, or 201 with `email_confirmation_required` when
    the project requires confirmation and no session was issued.

    Records the attempt either way (FA-06). **The recording changes nothing a
    caller can observe** — same status, same body, same headers — which is the
    property that makes it safe to record a failure at all.
    """
    try:
        session = auth_service.sign_up(request.email, request.password)
    except CredentialsRejectedError as error:
        _record_failure(events, SecurityEventType.SIGN_UP)

        # 400, not 401: nothing was being authenticated. The message is
        # deliberately generic — "User already registered" would turn this
        # endpoint into an account-enumeration oracle.
        #
        # Caught here rather than in a handler because it is endpoint-specific:
        # the same exception from `sign_in` correctly means 401, and a
        # handler cannot tell the two apart. Every other `AuthError` falls
        # through to `app.core.errors`.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration could not be completed",
        ) from error

    if session is None:
        # An unconfirmed registration. Recorded as a success because the
        # *registration* succeeded — what has not happened yet is confirmation,
        # and no user id exists to attach until it does.
        _record_success(events, SecurityEventType.SIGN_UP)

        return SignUpResponse(
            user_id=None,
            email_confirmation_required=True,
            session=None,
        )

    _record_success(events, SecurityEventType.SIGN_UP, user_id=AuthService.subject_of(session))

    return SignUpResponse(
        user_id=session.user_id,
        email_confirmation_required=False,
        session=_to_response(session),
    )


@router.post("/sign-in", response_model=SessionResponse, summary="Sign in")
def sign_in(
    request: SignInRequest,
    auth_service: AuthServiceDep,
    events: SecurityEventServiceDep,
) -> SessionResponse:
    """Exchange an email and password for a session.

    Records the outcome (FA-06) and **re-raises unchanged**. The exception
    continues to `app.core.errors`, which owns the mapping to a status code, so
    recording adds an observation without taking over the translation — a
    caller cannot tell from the response that anything was recorded, and cannot
    tell an existing account from an unknown one.
    """
    try:
        session = auth_service.sign_in(request.email, request.password)
    except CredentialsRejectedError:
        _record_failure(events, SecurityEventType.SIGN_IN)
        raise

    _record_success(events, SecurityEventType.SIGN_IN, user_id=AuthService.subject_of(session))

    return _to_response(session)


@router.post("/sign-out", response_model=MessageResponse, summary="Sign out")
def sign_out(
    access_token: AccessTokenDep,
    auth_service: AuthServiceDep,
    events: SecurityEventServiceDep,
) -> MessageResponse:
    """Revoke the session behind the supplied token.

    Requires a bearer token because it revokes *that* session upstream. A
    client-side discard would leave the token valid until it expired, which is
    not what signing out means.

    **`AccessTokenDep`, not `CurrentUserDep`, and that distinction is
    load-bearing.** This route requires a token to be *present*, not to verify.
    Signing out with an already-expired access token is an ordinary client
    situation, and Supabase's `/logout` revokes the whole session — the refresh
    token included — so that caller must still get through. Demanding a
    verified identity here to obtain a `user_id` for the audit record would
    reject them with a 401 and leave their refresh token alive until it expired
    on its own: a security regression in the one scenario sign-out exists for,
    traded for a nicer log line.

    So the event is recorded **without** a user id. An unverified token cannot
    tell us whose session this is, and recording an id we did not verify would
    be worse than recording none — the correlation id ties the event to the
    request either way.
    """
    auth_service.sign_out(access_token)

    _record_success(events, SecurityEventType.SIGN_OUT)

    return MessageResponse(message="Signed out")


@router.post("/refresh", response_model=SessionResponse, summary="Refresh a session")
def refresh(
    request: RefreshRequest,
    auth_service: AuthServiceDep,
    events: SecurityEventServiceDep,
) -> SessionResponse:
    """Exchange a refresh token for a new session.

    A spent or stolen refresh token being replayed is one of the clearest
    signals available that something is wrong, so the failure is recorded — and
    re-raised unchanged, like `sign_in`.
    """
    try:
        session = auth_service.refresh(request.refresh_token)
    except CredentialsRejectedError:
        _record_failure(events, SecurityEventType.TOKEN_REFRESH)
        raise

    _record_success(
        events, SecurityEventType.TOKEN_REFRESH, user_id=AuthService.subject_of(session)
    )

    return _to_response(session)


@router.get("/me", response_model=ProfileResponse, summary="The caller's profile")
def read_me(user: CurrentUserDep, auth_service: AuthServiceDep) -> ProfileResponse:
    """Return the profile of the authenticated caller.

    Also the endpoint that proves identity reaches the database: the row comes
    back keyed to the verified `sub` claim, and is provisioned on first use if
    the identity predates this API.
    """
    profile = auth_service.profile_for(user)

    return ProfileResponse(
        id=str(profile.id),
        email=profile.email,
        display_name=profile.display_name,
    )


@router.patch("/me", response_model=ProfileResponse, summary="Update the caller's profile")
def update_me(
    request: ProfileUpdateRequest,
    user: CurrentUserDep,
    connection: TenantConnectionDep,
) -> ProfileResponse:
    """Change the caller's display name.

    The row written is always the caller's own, and there are two independent
    reasons it cannot be anyone else's: the schema carries no id, and the
    `users_update_self` policy scopes the UPDATE to `id = auth.uid()` with a
    matching `WITH CHECK` so the row cannot be reassigned to another identity on
    the way out. The `WHERE id = %s` below is a filter, not the control.

    `email` is deliberately not updatable -- see `app.schemas.settings`. The
    address is authoritative upstream and reconciled on every authenticated
    request, so a write here would silently revert.

    Runs over the tenant connection rather than through `AuthService`, which
    holds the *privileged* `UserRepository` for provisioning. Routing an
    ordinary self-service edit through the one path that can write any user's row
    would widen a deliberately narrow bypass (`UserRepository` module docstring).

    Raises:
        HTTPException: 404 when the caller's profile row is not visible, which
            after a verified token means it was soft-deleted mid-request.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE public.users SET display_name = %s
            WHERE id = %s AND deleted_at IS NULL
            RETURNING id, email, display_name
            """,
            (request.display_name, user.id),
        )
        row = cursor.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )

    return ProfileResponse(id=str(row[0]), email=row[1], display_name=row[2])
