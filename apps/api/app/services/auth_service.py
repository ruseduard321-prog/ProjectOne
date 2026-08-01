"""Authentication business logic.

Holds no HTTP types and returns no HTTP types, so it is testable without the web
framework around it (CLAUDE.md §12). Routers translate what happens here into
status codes; the decisions themselves live here.
"""

import uuid

from app.core.security import IdentityProviderError
from app.repositories.supabase_auth import AuthSession, SupabaseAuthRepository
from app.repositories.users import UserProfile, UserRepository
from app.services.token_service import AuthenticatedUser, TokenService


class AuthService:
    """Registers, authenticates and signs out users."""

    def __init__(
        self,
        auth_repository: SupabaseAuthRepository,
        user_repository: UserRepository,
        token_service: TokenService,
    ) -> None:
        """Store the identity provider, the profile store and the verifier."""
        self._auth = auth_repository
        self._users = user_repository
        self._tokens = token_service

    def sign_up(self, email: str, password: str) -> AuthSession | None:
        """Register an identity and provision its profile row.

        Returns:
            The session, or None when email confirmation is required.

        Raises:
            CredentialsRejectedError: The address or password was rejected.
            IdentityProviderError: Supabase was unreachable.
        """
        session = self._auth.sign_up(email, password)

        if session is None:
            # No session means the identity exists but is unconfirmed. The
            # profile row is deliberately not created yet: `ensure_profile` runs
            # on the first authenticated request instead, so an abandoned
            # unconfirmed sign-up leaves no orphaned profile behind.
            return None

        self._provision(session)

        return session

    def sign_in(self, email: str, password: str) -> AuthSession:
        """Authenticate an identity and reconcile its profile row.

        Raises:
            CredentialsRejectedError: The credentials are wrong.
            IdentityProviderError: Supabase was unreachable.
        """
        session = self._auth.sign_in(email, password)
        self._provision(session)
        return session

    def sign_out(self, access_token: str) -> None:
        """Revoke the session behind an access token.

        Raises:
            IdentityProviderError: Supabase was unreachable.
        """
        self._auth.sign_out(access_token)

    def refresh(self, refresh_token: str) -> AuthSession:
        """Exchange a refresh token for a new session.

        Raises:
            CredentialsRejectedError: The refresh token is spent or invalid.
            IdentityProviderError: Supabase was unreachable.
        """
        session = self._auth.refresh(refresh_token)
        self._provision(session)
        return session

    def authenticate(self, token: str) -> AuthenticatedUser:
        """Return the identity a bearer token proves.

        Raises:
            InvalidTokenError: The token is missing, malformed or expired.
            SigningKeyUnavailableError: The signing key could not be fetched.
        """
        return self._tokens.verify(token)

    def profile_for(self, user: AuthenticatedUser) -> UserProfile:
        """Return the caller's profile row, provisioning it if absent.

        Reconciliation happens on read because that is the only moment a
        verified address is guaranteed to be in hand. An identity created
        outside this API — in the Supabase dashboard, say — gets its profile row
        here, on first use.
        """
        if user.email is None:
            # Every Supabase email/password identity carries one. A token
            # without it is a shape this code does not know how to provision,
            # and guessing an address would create a row keyed to a fiction.
            raise IdentityProviderError("Verified token carries no email address")

        return self._users.ensure_profile(user.id, user.email)

    def _provision(self, session: AuthSession) -> None:
        """Create or reconcile the profile row behind a freshly issued session.

        The user id is read from the **verified access token**, not from the
        response body around it. Both should agree, and the token is the one
        that has been cryptographically checked — trusting the envelope instead
        would make profile provisioning depend on an unverified field.
        """
        verified = self._tokens.verify(session.access_token)

        email = verified.email or session.email

        if email is None:
            raise IdentityProviderError("Supabase issued a session with no email address")

        self._users.ensure_profile(verified.id, email)

    @staticmethod
    def subject_of(session: AuthSession) -> uuid.UUID:
        """Return a session's user id as a uuid."""
        return uuid.UUID(session.user_id)
