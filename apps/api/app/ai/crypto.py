"""Encryption for BYOK provider keys at rest.

A stored provider key authorizes spend on an account ProjectOne does not own, so
a leak is a direct financial loss for the customer. RLS stops one tenant reading
another's row; this stops a leaked backup, a mis-scoped support query, or some
future admin path from yielding a *usable* credential. Both are required,
because each covers a failure mode the other does not (CLAUDE.md §16).

## AES-256-GCM, via `cryptography`

Already a dependency -- `pyjwt[crypto]` pulls it in for ES256 signature
verification (STEP-10), so this adds nothing to the dependency surface
(CLAUDE.md §28).

**GCM rather than CBC or Fernet.** GCM is authenticated: ciphertext that has
been altered fails to decrypt rather than decrypting to garbage that then gets
sent to a provider as a credential. Fernet would also work and is harder to
misuse, but it is AES-128-CBC + HMAC under the hood; GCM is the stronger
primitive and the nonce discipline it needs is enforced below rather than left
to a caller.

## A fresh nonce per encryption, never reused

GCM's one catastrophic failure mode is nonce reuse under the same key: it leaks
the XOR of two plaintexts and destroys the authentication guarantee. `os.urandom`
per call, prepended to the ciphertext, is what makes reuse structurally
impossible -- there is no code path that can supply one.

## The stored format

    base64( nonce[12] || ciphertext || tag[16] )

Self-contained, so decryption needs only the environment key. One base64 string
rather than three columns, because a format split across columns is one a future
migration can partially update.
"""

from __future__ import annotations

import base64
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

#: AES-GCM's standard nonce length. 96 bits is the size the mode is defined and
#: optimised for; other lengths are permitted but require extra derivation.
_NONCE_BYTES = 12

#: AES-256 requires a 32-byte key. Stated so a mis-sized configured key fails at
#: startup with a clear message rather than inside `AESGCM()`.
_KEY_BYTES = 32


class CredentialEncryptionError(Exception):
    """Encryption or decryption failed.

    Deliberately carries no detail about *why* in its public message. A
    decryption failure distinguishes "wrong key" from "corrupted ciphertext" in
    the log, where it is a debugging aid, and nowhere else.
    """

    public_message = "The stored credential could not be read"


class CredentialCipher:
    """Encrypts and decrypts provider keys with a single environment secret.

    One key for the whole deployment rather than one per workspace. Per-tenant
    keys would be stronger and require a key management service to be worth
    anything -- storing per-tenant keys in the same database as the ciphertext
    they protect is theatre, not defence. That is a real architecture decision
    (an ADR, and infrastructure), not something to improvise inside this step.
    """

    def __init__(self, key: bytes) -> None:
        """Store the AES key.

        Args:
            key: Exactly 32 bytes.

        Raises:
            CredentialEncryptionError: if the key is the wrong length. Raised
                rather than padded or hashed into shape: silently accepting a
                short key would mean a deployment believing it had AES-256 when
                it had something weaker.
        """
        if len(key) != _KEY_BYTES:
            raise CredentialEncryptionError(
                f"Encryption key must be {_KEY_BYTES} bytes, got {len(key)}"
            )

        self._cipher = AESGCM(key)

    def encrypt(self, plaintext: str) -> str:
        """Return `plaintext` encrypted, base64-encoded with its nonce.

        Args:
            plaintext: The provider key. Never logged by this method, and the
                caller must not log it either.

        Returns:
            An opaque string safe to store in `provider_credentials.encrypted_key`.
        """
        nonce = os.urandom(_NONCE_BYTES)
        ciphertext = self._cipher.encrypt(nonce, plaintext.encode("utf-8"), None)

        return base64.b64encode(nonce + ciphertext).decode("ascii")

    def decrypt(self, stored: str) -> str:
        """Return the plaintext behind a stored value.

        Raises:
            CredentialEncryptionError: if the value is malformed, was encrypted
                under a different key, or has been tampered with. GCM's
                authentication tag is what makes the last case detectable rather
                than silently producing a wrong key that gets sent to a provider.
        """
        try:
            raw = base64.b64decode(stored, validate=True)
        except (ValueError, TypeError) as error:
            raise CredentialEncryptionError("Stored credential is not valid base64") from error

        if len(raw) <= _NONCE_BYTES:
            raise CredentialEncryptionError("Stored credential is too short to contain a nonce")

        try:
            plaintext = self._cipher.decrypt(raw[:_NONCE_BYTES], raw[_NONCE_BYTES:], None)
        except InvalidTag as error:
            # Wrong key or tampered ciphertext -- GCM cannot distinguish the two,
            # and neither can this. Both mean the value is unusable.
            raise CredentialEncryptionError(
                "Stored credential failed authentication: wrong key or tampered ciphertext"
            ) from error

        return plaintext.decode("utf-8")


def parse_encryption_key(configured: str) -> bytes:
    """Decode a base64 encryption key from configuration.

    Base64 rather than raw bytes because the value travels through an
    environment variable, and a 32-byte binary blob does not survive that
    reliably.

    Args:
        configured: The base64-encoded 32-byte key.

    Returns:
        The decoded key.

    Raises:
        CredentialEncryptionError: if the value is not valid base64 or is the
            wrong length. Both are fatal at startup rather than at first use --
            a deployment that cannot decrypt its own credentials should not
            start and then fail on a user's request (CLAUDE.md §28a).
    """
    try:
        key = base64.b64decode(configured, validate=True)
    except (ValueError, TypeError) as error:
        raise CredentialEncryptionError(
            "Encryption key is not valid base64. Generate one with: "
            'python -c "import base64,os; print(base64.b64encode(os.urandom(32)).decode())"'
        ) from error

    if len(key) != _KEY_BYTES:
        raise CredentialEncryptionError(
            f"Encryption key must decode to {_KEY_BYTES} bytes, got {len(key)}"
        )

    return key
