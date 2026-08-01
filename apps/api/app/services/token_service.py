"""Access token verification.

Token verification is business logic and belongs in a service, not in a router
(CLAUDE.md §12) — the router's job is to translate a rejection into a 401, not
to decide what makes a token valid.

**Why asymmetric verification.** This Supabase project signs access tokens with
`ES256` (verified against the live project during STEP-10, not assumed). The API
therefore verifies with the *public* key published at the project's JWKS
endpoint and never holds a signing secret at all: a read-only copy of this
service cannot mint a token, only check one. The legacy Supabase model used a
shared `HS256` secret, where the verifier and the issuer hold the same key and
anything able to check a token can also forge one.
"""

import time
import uuid
from dataclasses import dataclass

import jwt
from jwt import PyJWKClient

from app.core.config import Settings
from app.core.security import InvalidTokenError, SigningKeyUnavailableError

# Supabase issues `ES256`. Pinned to an explicit allow-list rather than reading
# the algorithm from the token's own header, which is the classic JWT
# vulnerability: a token claiming `alg: none`, or claiming HMAC so the verifier
# uses a public key as a shared secret, is accepted by a verifier that trusts
# the header. PyJWT requires this argument for exactly that reason.
_ALLOWED_ALGORITHMS = ["ES256"]

# The `aud` claim Supabase sets on a signed-in user's access token.
_EXPECTED_AUDIENCE = "authenticated"


@dataclass(frozen=True)
class AuthenticatedUser:
    """The verified identity behind a request.

    Frozen because nothing downstream may adjust who the caller is — a mutable
    identity object is one careless assignment away from a privilege escalation.

    Attributes:
        id: The `sub` claim — the same value as `auth.users.id`, and what is
            set as `request.jwt.claim.sub` so `auth.uid()` resolves inside the
            RLS policies.
        email: The address on the token, authoritative over the denormalized
            copy in `public.users`.
    """

    id: uuid.UUID
    email: str | None


class TokenService:
    """Verifies Supabase-issued access tokens."""

    def __init__(self, settings: Settings, jwk_client: PyJWKClient) -> None:
        """Store the settings and the JWKS client used to resolve signing keys."""
        self._settings = settings
        self._jwk_client = jwk_client

    def verify(self, token: str) -> AuthenticatedUser:
        """Return the identity a token proves, or raise.

        Every check here is a check that something *must* pass, not a
        best-effort inspection. In particular the issuer and audience are
        verified alongside the signature: a signature check alone accepts a
        perfectly-signed token minted by a different Supabase project, which
        would let anyone with their own free project authenticate here.

        Args:
            token: The bare JWT, with no `Bearer ` prefix.

        Returns:
            The verified identity.

        Raises:
            InvalidTokenError: The token is malformed, expired, carries the
                wrong issuer or audience, or fails signature verification.
            SigningKeyUnavailableError: The signing key could not be fetched.
        """
        if not token:
            raise InvalidTokenError("No token supplied")

        try:
            signing_key = self._jwk_client.get_signing_key_from_jwt(token)
        except jwt.PyJWKClientError as error:
            # Covers both a network failure reaching JWKS and a token whose
            # `kid` matches no published key. Neither is the caller proving
            # anything, so neither may be honoured.
            raise SigningKeyUnavailableError(f"Could not resolve signing key: {error}") from error

        try:
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=_ALLOWED_ALGORITHMS,
                audience=_EXPECTED_AUDIENCE,
                issuer=self._settings.jwt_issuer,
                options={
                    # Named explicitly rather than relying on defaults, so that
                    # a future PyJWT default change cannot quietly disable one
                    # of them. `require` makes a token *missing* one of these
                    # claims a failure, which is not the same as verifying the
                    # value and is the gap a forged minimal token walks through.
                    "require": ["exp", "iat", "sub", "aud", "iss"],
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_aud": True,
                    "verify_iss": True,
                },
            )
        except jwt.InvalidTokenError as error:
            # PyJWT's whole failure hierarchy descends from InvalidTokenError:
            # expiry, bad signature, wrong audience, wrong issuer, missing
            # claim. All of them mean the same thing to a caller — rejected —
            # and the specific reason is preserved here for the log only.
            raise InvalidTokenError(f"Token rejected: {error}") from error

        subject = claims.get("sub")

        try:
            user_id = uuid.UUID(str(subject))
        except (ValueError, TypeError) as error:
            # `sub` is set as a session variable that `auth.uid()` casts to
            # uuid. A non-uuid value would surface as a database error deep in a
            # query rather than as an authentication failure here.
            raise InvalidTokenError(f"Token subject is not a uuid: {subject!r}") from error

        email = claims.get("email")

        return AuthenticatedUser(
            id=user_id,
            email=email if isinstance(email, str) and email else None,
        )


def build_jwk_client(jwks_url: str, cache_seconds: int, timeout_seconds: int) -> PyJWKClient:
    """Construct the JWKS client the token service verifies signatures with.

    Built once per process rather than per request: it caches the fetched key
    set, and a client rebuilt per request would fetch JWKS on every single
    call — turning Supabase into a hard dependency of every request and adding
    a network round trip to each one.

    `lifespan` bounds that cache so a key rotation is picked up without a
    restart. Without it, the process would keep rejecting valid tokens signed by
    the new key until someone redeployed.

    Takes primitives rather than `Settings` so the caller can memoize it — a
    pydantic model is unhashable and cannot be an `lru_cache` key.
    """
    return PyJWKClient(
        jwks_url,
        cache_keys=True,
        lifespan=cache_seconds,
        timeout=timeout_seconds,
    )


def seconds_until(expires_at: int) -> int:
    """Return how long until a unix timestamp, floored at zero."""
    return max(0, expires_at - int(time.time()))
