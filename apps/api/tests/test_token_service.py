"""Tests for access token verification.

These run offline. Tokens are minted here with a locally generated EC key, and
the JWKS client is substituted, so the suite never depends on Supabase being
reachable — while still exercising real ES256 signature verification rather than
a stub that returns True.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from pydantic import SecretStr

from app.core.config import Environment, Settings
from app.core.security import InvalidTokenError, SigningKeyUnavailableError
from app.services.token_service import TokenService
from tests.conftest import TEST_BYOK_KEY

ISSUER = "https://project.test/auth/v1"


@pytest.fixture(scope="module")
def signing_key() -> ec.EllipticCurvePrivateKey:
    """Return an EC P-256 private key — the curve ES256 is defined over."""
    return ec.generate_private_key(ec.SECP256R1())


@pytest.fixture
def settings() -> Settings:
    """Build Settings whose issuer matches the tokens minted below."""
    return Settings(
        environment=Environment.DEVELOPMENT,
        SUPABASE_URL="https://project.test",
        SUPABASE_SECRET_KEY=SecretStr("unused"),
        DATABASE_URL=SecretStr("postgresql://unused/db"),
        REQUEST_DATABASE_URL=SecretStr("postgresql://unused/db"),
        byok_encryption_key=SecretStr(TEST_BYOK_KEY),
        _env_file=None,
    )


class StubJWKClient:
    """Returns a fixed verification key, standing in for the JWKS endpoint."""

    def __init__(self, key: object, error: Exception | None = None) -> None:
        self._key = key
        self._error = error

    def get_signing_key_from_jwt(self, token: str) -> object:
        if self._error is not None:
            raise self._error
        return type("SigningKey", (), {"key": self._key})()


def make_token(
    signing_key: ec.EllipticCurvePrivateKey,
    *,
    subject: str | None = None,
    issuer: str = ISSUER,
    audience: str = "authenticated",
    expires_in: int = 3600,
    algorithm: str = "ES256",
    omit: tuple[str, ...] = (),
    email: str | None = "user@example.test",
) -> str:
    """Mint a signed token, with knobs for each thing verification must reject."""
    now = datetime.now(UTC)
    claims: dict[str, Any] = {
        "sub": subject or str(uuid.uuid4()),
        "iss": issuer,
        "aud": audience,
        "role": "authenticated",
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }

    if email is not None:
        claims["email"] = email

    for name in omit:
        claims.pop(name, None)

    return jwt.encode(claims, signing_key, algorithm=algorithm)


@pytest.fixture
def service(settings: Settings, signing_key: ec.EllipticCurvePrivateKey) -> TokenService:
    """Return a token service verifying against the local key."""
    return TokenService(settings, StubJWKClient(signing_key.public_key()))


def test_a_valid_token_yields_its_identity(
    service: TokenService, signing_key: ec.EllipticCurvePrivateKey
) -> None:
    subject = uuid.uuid4()
    token = make_token(signing_key, subject=str(subject))

    user = service.verify(token)

    assert user.id == subject
    assert user.email == "user@example.test"


def test_a_missing_token_is_rejected(service: TokenService) -> None:
    with pytest.raises(InvalidTokenError):
        service.verify("")


def test_a_malformed_token_is_rejected(service: TokenService) -> None:
    with pytest.raises((InvalidTokenError, SigningKeyUnavailableError)):
        service.verify("not-a-jwt")


def test_an_expired_token_is_rejected(
    service: TokenService, signing_key: ec.EllipticCurvePrivateKey
) -> None:
    token = make_token(signing_key, expires_in=-60)

    with pytest.raises(InvalidTokenError):
        service.verify(token)


def test_a_tampered_token_is_rejected(
    service: TokenService, signing_key: ec.EllipticCurvePrivateKey
) -> None:
    """A token re-signed by a different key must fail verification.

    The realistic forgery: an attacker who knows the token's shape mints their
    own with a key they control. Only the signature check stops it.
    """
    attacker_key = ec.generate_private_key(ec.SECP256R1())
    forged = make_token(attacker_key, subject=str(uuid.uuid4()))

    with pytest.raises(InvalidTokenError):
        service.verify(forged)


def test_a_token_from_another_issuer_is_rejected(
    service: TokenService, signing_key: ec.EllipticCurvePrivateKey
) -> None:
    """Correctly signed, wrong project — must still be rejected.

    Without an issuer check, anyone could point their own free Supabase project
    at this API and authenticate as whoever they liked.
    """
    token = make_token(signing_key, issuer="https://attacker.test/auth/v1")

    with pytest.raises(InvalidTokenError):
        service.verify(token)


def test_a_token_with_the_wrong_audience_is_rejected(
    service: TokenService, signing_key: ec.EllipticCurvePrivateKey
) -> None:
    token = make_token(signing_key, audience="anon")

    with pytest.raises(InvalidTokenError):
        service.verify(token)


@pytest.mark.parametrize("claim", ["exp", "sub", "iss", "aud", "iat"])
def test_a_token_missing_a_required_claim_is_rejected(
    service: TokenService, signing_key: ec.EllipticCurvePrivateKey, claim: str
) -> None:
    """Verifying a claim's value is not the same as requiring it to exist."""
    token = make_token(signing_key, omit=(claim,))

    with pytest.raises(InvalidTokenError):
        service.verify(token)


def test_a_non_uuid_subject_is_rejected(
    service: TokenService, signing_key: ec.EllipticCurvePrivateKey
) -> None:
    """`sub` is cast to uuid by auth.uid(); a bad one must fail here, not there."""
    token = make_token(signing_key, subject="not-a-uuid")

    with pytest.raises(InvalidTokenError):
        service.verify(token)


def test_an_unavailable_signing_key_is_not_treated_as_a_valid_token(
    settings: Settings, signing_key: ec.EllipticCurvePrivateKey
) -> None:
    """A JWKS outage must reject, never admit."""
    service = TokenService(
        settings, StubJWKClient(None, error=jwt.PyJWKClientError("JWKS unreachable"))
    )

    with pytest.raises(SigningKeyUnavailableError):
        service.verify(make_token(signing_key))


def test_an_hmac_token_is_rejected(
    service: TokenService, signing_key: ec.EllipticCurvePrivateKey
) -> None:
    """The algorithm-confusion attack must not work.

    A verifier that reads `alg` from the token's own header can be handed an
    HS256 token and will use the ES256 *public* key as an HMAC secret — and that
    key is public. Pinning the algorithm list is what prevents it.
    """
    forged = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "iss": ISSUER,
            "aud": "authenticated",
            "iat": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        "public-key-as-a-shared-secret",
        algorithm="HS256",
    )

    with pytest.raises((InvalidTokenError, SigningKeyUnavailableError)):
        service.verify(forged)
