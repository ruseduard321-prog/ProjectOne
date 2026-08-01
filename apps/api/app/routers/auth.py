"""Authentication router.

Validates input, calls the service, returns a response — nothing else
(CLAUDE.md §12). The only decision made here is which HTTP status an outcome
maps to, which is precisely what this layer owns.
"""

from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import AccessTokenDep, AuthServiceDep, CurrentUserDep
from app.core.security import (
    AuthError,
    CredentialsRejectedError,
    IdentityProviderError,
)
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

router = APIRouter(prefix="/auth", tags=["auth"])


def _to_response(session: AuthSession) -> SessionResponse:
    """Convert a service-layer session into its response shape."""
    return SessionResponse(
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        expires_in=session.expires_in,
        user_id=session.user_id,
        email=session.email,
    )


def _reject(error: AuthError) -> HTTPException:
    """Map an authentication failure onto a status code.

    `IdentityProviderError` is a 503 because it is genuinely ours: Supabase is
    unreachable and the caller's credentials were never actually judged.
    Returning 401 there would tell a user their password is wrong during an
    outage, and would hide the outage in the one metric that should reveal it.
    """
    if isinstance(error, IdentityProviderError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error.public_message,
        )

    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=error.public_message,
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post(
    "/sign-up",
    response_model=SignUpResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new account",
)
def sign_up(request: SignUpRequest, auth_service: AuthServiceDep) -> SignUpResponse:
    """Register an identity and provision its ProjectOne profile.

    Returns 201 with a session, or 201 with `email_confirmation_required` when
    the project requires confirmation and no session was issued.
    """
    try:
        session = auth_service.sign_up(request.email, request.password)
    except CredentialsRejectedError as error:
        # 400, not 401: nothing was being authenticated. The message is
        # deliberately generic — "User already registered" would turn this
        # endpoint into an account-enumeration oracle.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration could not be completed",
        ) from error
    except AuthError as error:
        raise _reject(error) from error

    if session is None:
        return SignUpResponse(
            user_id=None,
            email_confirmation_required=True,
            session=None,
        )

    return SignUpResponse(
        user_id=session.user_id,
        email_confirmation_required=False,
        session=_to_response(session),
    )


@router.post("/sign-in", response_model=SessionResponse, summary="Sign in")
def sign_in(request: SignInRequest, auth_service: AuthServiceDep) -> SessionResponse:
    """Exchange an email and password for a session."""
    try:
        session = auth_service.sign_in(request.email, request.password)
    except AuthError as error:
        raise _reject(error) from error

    return _to_response(session)


@router.post("/sign-out", response_model=MessageResponse, summary="Sign out")
def sign_out(access_token: AccessTokenDep, auth_service: AuthServiceDep) -> MessageResponse:
    """Revoke the session behind the supplied token.

    Requires a bearer token because it revokes *that* session upstream. A
    client-side discard would leave the token valid until it expired, which is
    not what signing out means.
    """
    try:
        auth_service.sign_out(access_token)
    except AuthError as error:
        raise _reject(error) from error

    return MessageResponse(message="Signed out")


@router.post("/refresh", response_model=SessionResponse, summary="Refresh a session")
def refresh(request: RefreshRequest, auth_service: AuthServiceDep) -> SessionResponse:
    """Exchange a refresh token for a new session."""
    try:
        session = auth_service.refresh(request.refresh_token)
    except AuthError as error:
        raise _reject(error) from error

    return _to_response(session)


@router.get("/me", response_model=ProfileResponse, summary="The caller's profile")
def read_me(user: CurrentUserDep, auth_service: AuthServiceDep) -> ProfileResponse:
    """Return the profile of the authenticated caller.

    Also the endpoint that proves identity reaches the database: the row comes
    back keyed to the verified `sub` claim, and is provisioned on first use if
    the identity predates this API.
    """
    try:
        profile = auth_service.profile_for(user)
    except AuthError as error:
        raise _reject(error) from error

    return ProfileResponse(
        id=str(profile.id),
        email=profile.email,
        display_name=profile.display_name,
    )
