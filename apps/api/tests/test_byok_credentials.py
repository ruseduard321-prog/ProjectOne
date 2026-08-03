"""BYOK encryption, and the rule that a provider key never reaches a log.

The validation STEP-17 asks for is specific: "a BYOK key never appears in a log
or an API response, verified by grepping captured output rather than by review."
`TestAKeyNeverReachesALog` does exactly that -- it captures real log output
through the real logging pipeline and searches it, rather than reading the code
and concluding it looks fine.
"""

from __future__ import annotations

import base64
import logging
import os
import uuid

import pytest

from app.ai.crypto import (
    CredentialCipher,
    CredentialEncryptionError,
    parse_encryption_key,
)
from app.ai.errors import NoProviderAvailableError
from app.core.logging import configure_logging, redact
from app.repositories.provider_credentials import CredentialSummary, StoredCredential
from app.services.provider_credential_service import ProviderCredentialService

#: A realistic-looking key. Shaped like a real one so the redaction assertions
#: are meaningful rather than passing on a value no filter would match anyway.
PLAINTEXT_KEY = "sk-proj-Ab3dEfGh1jKlMn0pQrStUvWxYz2345678"  # noqa: S105 - test fixture


def a_cipher() -> CredentialCipher:
    """Return a cipher with a fresh random key."""
    return CredentialCipher(os.urandom(32))


class FakeRepository:
    """An in-memory stand-in for `ProviderCredentialRepository`."""

    def __init__(self) -> None:
        self.rows: dict[tuple[uuid.UUID, str], StoredCredential] = {}
        self.stored_ciphertext: list[str] = []

    def credential_for(self, workspace_id: uuid.UUID, provider: str) -> StoredCredential | None:
        return self.rows.get((workspace_id, provider))

    def configured_providers(self, workspace_id: uuid.UUID) -> tuple[str, ...]:
        return tuple(sorted(provider for (ws, provider) in self.rows if ws == workspace_id))

    def list_summaries(self, workspace_id: uuid.UUID) -> tuple[CredentialSummary, ...]:
        return tuple(
            CredentialSummary(id=row.id, provider=row.provider, last_four=row.last_four)
            for (ws, _), row in self.rows.items()
            if ws == workspace_id
        )

    def store(
        self,
        workspace_id: uuid.UUID,
        provider: str,
        encrypted_key: str,
        last_four: str,
        created_by: uuid.UUID,
    ) -> uuid.UUID:
        credential_id = uuid.uuid4()
        self.stored_ciphertext.append(encrypted_key)
        self.rows[(workspace_id, provider)] = StoredCredential(
            id=credential_id,
            provider=provider,
            encrypted_key=encrypted_key,
            last_four=last_four,
        )
        return credential_id

    def revoke(self, workspace_id: uuid.UUID, provider: str) -> bool:
        return self.rows.pop((workspace_id, provider), None) is not None


class TestEncryption:
    """AES-256-GCM, with the nonce discipline the mode requires."""

    def test_a_key_round_trips(self) -> None:
        cipher = a_cipher()

        assert cipher.decrypt(cipher.encrypt(PLAINTEXT_KEY)) == PLAINTEXT_KEY

    def test_the_plaintext_is_not_present_in_the_ciphertext(self) -> None:
        cipher = a_cipher()

        stored = cipher.encrypt(PLAINTEXT_KEY)

        assert PLAINTEXT_KEY not in stored
        assert PLAINTEXT_KEY not in base64.b64decode(stored).decode("latin-1")

    def test_encrypting_twice_gives_different_ciphertext(self) -> None:
        # A fresh nonce per call. Identical ciphertext for identical input would
        # mean a fixed nonce -- GCM's one catastrophic failure mode, leaking the
        # XOR of two plaintexts and destroying authentication.
        cipher = a_cipher()

        assert cipher.encrypt(PLAINTEXT_KEY) != cipher.encrypt(PLAINTEXT_KEY)

    def test_a_different_key_cannot_decrypt(self) -> None:
        stored = a_cipher().encrypt(PLAINTEXT_KEY)

        with pytest.raises(CredentialEncryptionError):
            a_cipher().decrypt(stored)

    def test_tampered_ciphertext_is_rejected_rather_than_returning_garbage(self) -> None:
        # GCM's authentication tag. Without it, a flipped bit would decrypt to
        # a *wrong key* that then gets sent to a provider as a credential.
        cipher = a_cipher()
        raw = bytearray(base64.b64decode(cipher.encrypt(PLAINTEXT_KEY)))
        raw[-1] ^= 0x01

        with pytest.raises(CredentialEncryptionError):
            cipher.decrypt(base64.b64encode(bytes(raw)).decode("ascii"))

    def test_a_short_key_is_refused(self) -> None:
        # Silently padding would mean a deployment believing it had AES-256
        # while holding something weaker.
        with pytest.raises(CredentialEncryptionError):
            CredentialCipher(os.urandom(16))

    def test_malformed_stored_values_are_refused(self) -> None:
        cipher = a_cipher()

        with pytest.raises(CredentialEncryptionError):
            cipher.decrypt("not base64 at all !!!")

        with pytest.raises(CredentialEncryptionError):
            cipher.decrypt(base64.b64encode(b"short").decode("ascii"))

    def test_a_configured_key_is_parsed_from_base64(self) -> None:
        raw = os.urandom(32)

        assert parse_encryption_key(base64.b64encode(raw).decode("ascii")) == raw

    def test_a_wrong_length_configured_key_is_refused(self) -> None:
        with pytest.raises(CredentialEncryptionError):
            parse_encryption_key(base64.b64encode(os.urandom(16)).decode("ascii"))

    def test_a_non_base64_configured_key_is_refused(self) -> None:
        with pytest.raises(CredentialEncryptionError):
            parse_encryption_key("clearly-not-base64-!!!")


class TestCredentialService:
    """Storage, retrieval and the boundary plaintext never crosses."""

    def test_what_is_stored_is_ciphertext(self) -> None:
        repository = FakeRepository()
        service = ProviderCredentialService(repository, a_cipher())
        workspace = uuid.uuid4()

        service.store(workspace, "openai", PLAINTEXT_KEY, uuid.uuid4())

        assert PLAINTEXT_KEY not in repository.stored_ciphertext[0]

    def test_the_key_round_trips_through_the_service(self) -> None:
        repository = FakeRepository()
        service = ProviderCredentialService(repository, a_cipher())
        workspace = uuid.uuid4()

        service.store(workspace, "openai", PLAINTEXT_KEY, uuid.uuid4())

        assert service.key_for(workspace, "openai") == PLAINTEXT_KEY

    def test_only_the_last_four_characters_are_retained_for_display(self) -> None:
        repository = FakeRepository()
        service = ProviderCredentialService(repository, a_cipher())

        summary = service.store(uuid.uuid4(), "openai", PLAINTEXT_KEY, uuid.uuid4())

        assert summary.last_four == PLAINTEXT_KEY[-4:]
        assert len(summary.last_four) == 4

    def test_a_summary_has_no_field_that_could_carry_a_key(self) -> None:
        # Structural, not a matter of remembering to exclude it in a serializer:
        # a future endpoint returning this type cannot leak a key by accident.
        fields = set(CredentialSummary.__dataclass_fields__)

        assert fields == {"id", "provider", "last_four"}

    def test_a_missing_credential_is_an_honest_error(self) -> None:
        service = ProviderCredentialService(FakeRepository(), a_cipher())

        with pytest.raises(NoProviderAvailableError):
            service.key_for(uuid.uuid4(), "openai")

    def test_an_undecryptable_credential_does_not_leak_that_it_exists(self) -> None:
        # Deliberately the same error as "no credential": distinguishing them
        # would report on a row that RLS may have hidden.
        repository = FakeRepository()
        workspace = uuid.uuid4()
        ProviderCredentialService(repository, a_cipher()).store(
            workspace, "openai", PLAINTEXT_KEY, uuid.uuid4()
        )

        rotated = ProviderCredentialService(repository, a_cipher())

        with pytest.raises(NoProviderAvailableError):
            rotated.key_for(workspace, "openai")

    def test_an_implausibly_short_key_is_refused_before_anything_is_written(self) -> None:
        # A typo must not replace a working credential.
        repository = FakeRepository()
        service = ProviderCredentialService(repository, a_cipher())

        with pytest.raises(ValueError):
            service.store(uuid.uuid4(), "openai", "sk-1", uuid.uuid4())

        assert repository.stored_ciphertext == []

    def test_storing_again_replaces_the_previous_key(self) -> None:
        repository = FakeRepository()
        service = ProviderCredentialService(repository, a_cipher())
        workspace = uuid.uuid4()

        service.store(workspace, "openai", PLAINTEXT_KEY, uuid.uuid4())
        service.store(workspace, "openai", "sk-proj-replacement-key-9999", uuid.uuid4())

        assert service.key_for(workspace, "openai") == "sk-proj-replacement-key-9999"

    def test_revoking_removes_the_credential(self) -> None:
        repository = FakeRepository()
        service = ProviderCredentialService(repository, a_cipher())
        workspace = uuid.uuid4()
        service.store(workspace, "openai", PLAINTEXT_KEY, uuid.uuid4())

        assert service.revoke(workspace, "openai") is True
        assert service.configured_providers(workspace) == ()

    def test_revoking_nothing_reports_false(self) -> None:
        service = ProviderCredentialService(FakeRepository(), a_cipher())

        assert service.revoke(uuid.uuid4(), "openai") is False


class TestAKeyNeverReachesALog:
    """Verified by capturing real log output and searching it."""

    def test_the_redaction_filter_covers_provider_key_formats(self) -> None:
        # STEP-16's inherited note asked for this explicitly: confirm the
        # existing patterns cover provider key formats *before* the first key
        # is logged anywhere, rather than after.
        for rendered in (
            f"api_key={PLAINTEXT_KEY}",
            f"'api_key': '{PLAINTEXT_KEY}'",
            f'"apiKey": "{PLAINTEXT_KEY}"',
            f"Authorization: Bearer {PLAINTEXT_KEY}",
            f"secret={PLAINTEXT_KEY}",
        ):
            assert PLAINTEXT_KEY not in redact(rendered), rendered

    def test_storing_a_key_writes_no_key_to_the_log(self, caplog: pytest.LogCaptureFixture) -> None:
        service = ProviderCredentialService(FakeRepository(), a_cipher())

        with caplog.at_level(logging.DEBUG):
            service.store(uuid.uuid4(), "openai", PLAINTEXT_KEY, uuid.uuid4())

        assert PLAINTEXT_KEY not in caplog.text
        assert PLAINTEXT_KEY[-4:] not in caplog.text

    def test_reading_a_key_writes_no_key_to_the_log(self, caplog: pytest.LogCaptureFixture) -> None:
        repository = FakeRepository()
        service = ProviderCredentialService(repository, a_cipher())
        workspace = uuid.uuid4()
        service.store(workspace, "openai", PLAINTEXT_KEY, uuid.uuid4())
        caplog.clear()

        with caplog.at_level(logging.DEBUG):
            service.key_for(workspace, "openai")

        assert PLAINTEXT_KEY not in caplog.text

    def test_a_decryption_failure_logs_no_ciphertext_and_no_key(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        repository = FakeRepository()
        ProviderCredentialService(repository, a_cipher()).store(
            uuid.uuid4(), "openai", PLAINTEXT_KEY, uuid.uuid4()
        )
        workspace, provider = next(iter(repository.rows))
        ciphertext = repository.rows[(workspace, provider)].encrypted_key
        rotated = ProviderCredentialService(repository, a_cipher())

        with caplog.at_level(logging.DEBUG), pytest.raises(NoProviderAvailableError):
            rotated.key_for(workspace, provider)

        assert PLAINTEXT_KEY not in caplog.text
        assert ciphertext not in caplog.text

    def test_the_configured_pipeline_redacts_a_key_end_to_end(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Through the real handler, not a caplog shortcut: this is what a
        # production log line actually goes through, and it is the assertion
        # that would catch a handler misconfiguration.
        configure_logging()
        logging.getLogger("test.byok").warning("api_key=%s", PLAINTEXT_KEY)

        captured = capsys.readouterr()

        assert PLAINTEXT_KEY not in captured.out
        assert "[REDACTED]" in captured.out
