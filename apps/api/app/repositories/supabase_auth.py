"""Supabase Auth (GoTrue) HTTP client.

Identity lives in `auth.users`, owned by Supabase — passwords, MFA factors,
sessions, OAuth links and email confirmation are all its responsibility, not
ProjectOne's (Table - users). This repository is the only place that talks to
it, so swapping the identity provider later touches one file.

**On the STEP-07 401.** STEP-07 recorded that REST calls with the `sb_secret_...`
key returned 401 while direct PostgreSQL worked, and STEP-10 inherited it as a
blocker. It was a request-shape problem, not a credential problem: the key must
be sent in **both** the `apikey` header and `Authorization: Bearer`. With both
set, `/rest/v1/`, `/auth/v1/settings` and `/auth/v1/admin/users` all answer 200.
"""

from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import Settings
from app.core.security import CredentialsRejectedError, IdentityProviderError


@dataclass(frozen=True)
class AuthSession:
    """The tokens Supabase issues for a signed-in user."""

    access_token: str
    refresh_token: str
    expires_in: int
    user_id: str
    email: str | None


class SupabaseAuthRepository:
    """Reaches the Supabase Auth API."""

    def __init__(self, settings: Settings) -> None:
        """Store the settings holding the Supabase URL and service key."""
        self._settings = settings

    def _headers(self) -> dict[str, str]:
        """Return the headers every Supabase Auth call requires.

        Both are needed. `apikey` identifies the project; `Authorization`
        authorizes the call. Sending only one returns 401 — the STEP-07 symptom.
        """
        key = self._settings.supabase_secret_key.get_secret_value()
        return {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """POST to the Auth API and return the decoded body.

        Raises:
            CredentialsRejectedError: Supabase rejected the request (4xx).
            IdentityProviderError: Supabase was unreachable or failed (5xx).
        """
        url = f"{self._settings.supabase_auth_url}{path}"

        try:
            response = httpx.post(
                url,
                json=payload,
                headers=self._headers(),
                timeout=self._settings.supabase_timeout_seconds,
            )
        except httpx.HTTPError as error:
            # The URL is safe to log; the key is in a header, not the URL, and
            # is never included here (CLAUDE.md §25).
            raise IdentityProviderError(f"Supabase Auth unreachable at {path}: {error}") from error

        if response.status_code >= 500:
            raise IdentityProviderError(f"Supabase Auth returned {response.status_code} for {path}")

        if response.status_code >= 400:
            # A 4xx here is a rejected credential — a duplicate address, a wrong
            # password, a weak password. Supabase's own message is not passed
            # through: "User already registered" turns any sign-up form into an
            # account-enumeration oracle.
            raise CredentialsRejectedError(
                f"Supabase Auth rejected {path} with {response.status_code}"
            )

        try:
            body = response.json()
        except ValueError as error:
            raise IdentityProviderError(f"Supabase Auth returned non-JSON for {path}") from error

        if not isinstance(body, dict):
            raise IdentityProviderError(f"Supabase Auth returned unexpected JSON for {path}")

        return body

    def sign_up(self, email: str, password: str) -> AuthSession | None:
        """Register a new identity.

        Returns:
            The session, or None when the project requires email confirmation —
            in that case Supabase creates the user but issues no tokens, and the
            caller is not signed in yet. Returning None rather than raising
            keeps that a normal outcome, because it is one.

        Raises:
            CredentialsRejectedError: The address or password was rejected.
            IdentityProviderError: Supabase was unreachable.
        """
        body = self._post("/signup", {"email": email, "password": password})
        return self._to_session(body)

    def sign_in(self, email: str, password: str) -> AuthSession:
        """Exchange an email and password for a session.

        Raises:
            CredentialsRejectedError: The credentials are wrong.
            IdentityProviderError: Supabase was unreachable or malformed.
        """
        body = self._post("/token?grant_type=password", {"email": email, "password": password})
        session = self._to_session(body)

        if session is None:
            raise IdentityProviderError("Supabase Auth returned no session for a sign-in")

        return session

    def sign_out(self, access_token: str) -> None:
        """Revoke the session behind an access token.

        Called with the *user's* token rather than the service key: this revokes
        one session, and the token identifies which. A local discard would leave
        the token valid until expiry, so a "signed out" user still has working
        credentials — which is not what signing out means.

        Raises:
            IdentityProviderError: Supabase was unreachable.
        """
        url = f"{self._settings.supabase_auth_url}/logout"
        headers = self._headers()
        headers["Authorization"] = f"Bearer {access_token}"

        try:
            response = httpx.post(
                url, headers=headers, timeout=self._settings.supabase_timeout_seconds
            )
        except httpx.HTTPError as error:
            raise IdentityProviderError(f"Supabase Auth unreachable at /logout: {error}") from error

        # 401/403 means the token is already invalid, which is the state sign-out
        # is trying to reach. Treating that as an error would make signing out
        # twice fail for no useful reason.
        if response.status_code >= 500:
            raise IdentityProviderError(f"Supabase Auth returned {response.status_code} on logout")

    def refresh(self, refresh_token: str) -> AuthSession:
        """Exchange a refresh token for a new session.

        Raises:
            CredentialsRejectedError: The refresh token is spent or invalid.
            IdentityProviderError: Supabase was unreachable or malformed.
        """
        body = self._post("/token?grant_type=refresh_token", {"refresh_token": refresh_token})
        session = self._to_session(body)

        if session is None:
            raise IdentityProviderError("Supabase Auth returned no session for a refresh")

        return session

    @staticmethod
    def _to_session(body: dict[str, Any]) -> AuthSession | None:
        """Convert an Auth API body into a session, or None when none was issued."""
        access_token = body.get("access_token")
        refresh_token = body.get("refresh_token")

        if not isinstance(access_token, str) or not isinstance(refresh_token, str):
            return None

        # On /signup the user is the top-level body; on /token it is nested.
        user = body.get("user")
        user_object: dict[str, Any] = user if isinstance(user, dict) else body

        user_id = user_object.get("id")
        if not isinstance(user_id, str):
            return None

        email = user_object.get("email")
        expires_in = body.get("expires_in")

        return AuthSession(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in if isinstance(expires_in, int) else 3600,
            user_id=user_id,
            email=email if isinstance(email, str) else None,
        )
