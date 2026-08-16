"""Validation of the R2 storage configuration, at both levels it is checked.

**Two questions, deliberately answered in two places** (STEP-28):

- *Is this `Settings` object coherent?* All four values or none. One, two or
  three is a mistake, caught by `_reject_partial_storage_configuration`, so that
  three-of-four is never reported as the useless "storage is not configured".
  **Zero stays valid here** — it is what every test that never touches storage
  constructs, and what `StorageNotConfiguredError` names.
- *May this deployment start?* No. Since STEP-28 introduced the first real
  caller, `get_settings()` refuses to start without all four, because a missing
  value now means every upload fails in front of a user.

The split is the point. Folding the second question into the first would make a
storage-free `Settings` unconstructable and break roughly fifteen test modules
to express a rule that only ever applied to deployments.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.core.config import (
    STARTUP_REQUIRED_STORAGE_VARIABLES,
    Settings,
    _error_location,
    get_settings,
)
from tests.conftest import TEST_BYOK_KEY


@pytest.fixture(autouse=True)
def isolate_from_ambient_configuration(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Cut these tests off from the developer's real environment.

    Without this the suite is **environment-dependent in the worst way**: it
    passed on a machine with no R2 configured and failed on one with, because
    `Settings` reads `.env` and `PROJECTONE_*` variables. A case constructing a
    deliberately partial configuration would have the missing values quietly
    supplied from the ambient environment, so the assertion that partial input
    is rejected would be testing a *complete* input and failing.

    Both sources are removed: every `PROJECTONE_R2_*` variable, and the `.env`
    file itself (repointed at an empty file in a temp directory). What the test
    passes in is then the only configuration that exists, which is the only way
    these assertions mean what they say.
    """
    for name in (
        "PROJECTONE_R2_ACCOUNT_ID",
        "PROJECTONE_R2_BUCKET",
        "PROJECTONE_R2_ACCESS_KEY_ID",
        "PROJECTONE_R2_SECRET_ACCESS_KEY",
    ):
        monkeypatch.delenv(name, raising=False)

    empty_env = tmp_path / ".env"
    empty_env.write_text("", encoding="utf-8")
    monkeypatch.setitem(Settings.model_config, "env_file", str(empty_env))


#: Everything unrelated to storage that `Settings` requires. Storage validity is
#: what is under test, so the rest is held constant and valid.
BASE: dict[str, Any] = {
    "environment": "development",
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_SECRET_KEY": "service-key",
    "DATABASE_URL": "postgresql://postgres@localhost/db",
    "REQUEST_DATABASE_URL": "postgresql://authenticator@localhost/db",
    "byok_encryption_key": "A" * 44,
}

ALL_FOUR: dict[str, Any] = {
    "r2_account_id": "account-id",
    "r2_bucket": "projectone-assets",
    "r2_access_key_id": "access-key-id",
    "r2_secret_access_key": "super-secret-value",
}


class TestCompleteAndAbsentConfigurationsAreValid:
    """The two states a `Settings` object is allowed to be in."""

    def test_no_storage_configuration_is_valid_at_the_model_level(self) -> None:
        """A storage-free `Settings` must stay constructable.

        Not a relaxation of the STEP-28 requirement — that one is asserted in
        `TestStartupRequiresStorage` below, against `get_settings()`. This is the
        object the rest of the suite builds, and the state
        `build_storage_provider()` raises `StorageNotConfiguredError` for.
        """
        settings = Settings(**BASE)

        assert settings.storage_is_configured is False

    def test_all_four_values_are_valid(self) -> None:
        settings = Settings(**BASE, **ALL_FOUR)

        assert settings.storage_is_configured is True
        assert settings.r2_endpoint_url == "https://account-id.r2.cloudflarestorage.com"


class TestPartialConfigurationIsRejected:
    """The state that must never be silently equivalent to "unconfigured"."""

    @pytest.mark.parametrize(
        "present",
        [
            pytest.param(["r2_account_id"], id="1-of-4-account"),
            pytest.param(["r2_bucket"], id="1-of-4-bucket"),
            pytest.param(["r2_access_key_id"], id="1-of-4-access-key"),
            pytest.param(["r2_secret_access_key"], id="1-of-4-secret"),
            pytest.param(["r2_account_id", "r2_bucket"], id="2-of-4"),
            pytest.param(["r2_account_id", "r2_bucket", "r2_access_key_id"], id="3-of-4"),
            pytest.param(
                ["r2_account_id", "r2_bucket", "r2_secret_access_key"],
                id="3-of-4-missing-access-key",
            ),
        ],
    )
    def test_a_partial_configuration_fails_validation(self, present: list[str]) -> None:
        """Any non-empty proper subset of the four is a startup failure."""
        partial = {name: ALL_FOUR[name] for name in present}

        with pytest.raises(ValidationError):
            Settings(**BASE, **partial)

    def test_the_error_names_the_missing_variables(self) -> None:
        """An operator must learn *which* variable to set, not merely that one is.

        "Object storage is not configured" when three of four values are present
        is the least useful true statement available -- it points at the whole
        subsystem instead of the single omission.
        """
        with pytest.raises(ValidationError) as raised:
            Settings(
                **BASE,
                r2_account_id="account-id",
                r2_bucket="projectone-assets",
                r2_access_key_id="access-key-id",
            )

        message = str(raised.value)
        assert "PROJECTONE_R2_SECRET_ACCESS_KEY" in message
        # The three that *were* supplied are not reported as missing.
        assert "PROJECTONE_R2_BUCKET" not in message

    def test_the_startup_message_never_contains_a_secret_value(self) -> None:
        """The message that reaches a container log must carry no credential.

        **This test found a real leak.** Pydantic's default error rendering
        echoes the entire input mapping back in an `input_value=...` clause, and
        for a settings model that mapping is every credential the process was
        started with, in plaintext. `SecretStr` does not help: it masks a value
        once it is a *field*, while the echo happens on the raw input before
        validation assigns it.

        The fix is `errors(include_input=False)` plus hand-formatting in
        `get_settings()`, so what is printed is the variable name and the reason
        and nothing else. Asserted against that rendering rather than against
        `str(ValidationError)`, because the rendering is what an operator
        actually sees (CLAUDE.md §16, §25).

        This applies to every secret in the model, not only the R2 ones -- a
        malformed `DATABASE_URL` would have leaked the same way.
        """
        with pytest.raises(ValidationError) as raised:
            Settings(
                **BASE,
                r2_account_id="account-id",
                r2_secret_access_key="super-secret-value",
            )

        rendered = "\n".join(
            f"  - {_error_location(item)}: {item['msg']}"
            for item in raised.value.errors(include_input=False)
        )

        assert "super-secret-value" not in rendered
        assert "account-id" not in rendered
        # The operator still learns what to fix.
        assert "PROJECTONE_R2_BUCKET" in rendered

    def test_a_model_level_error_does_not_crash_the_startup_formatter(self) -> None:
        """Model-level errors carry an empty `loc`, which used to raise.

        `get_settings()` formatted `item['loc'][0]` unconditionally. A
        `model_validator` reports a relationship between fields rather than one
        field, so its `loc` is empty and the indexing raised `IndexError` --
        crashing inside the handler whose job is to explain the
        misconfiguration. The cross-field storage check is the first
        model-level validator here, which is what made the latent bug
        reachable.
        """
        with pytest.raises(ValidationError) as raised:
            Settings(**BASE, r2_account_id="account-id")

        for item in raised.value.errors(include_input=False):
            assert _error_location(item)  # no IndexError, and never empty


class TestSecretsStayHidden:
    """`SecretStr` must survive the round trip through settings."""

    def test_credentials_are_masked_in_repr(self) -> None:
        settings = Settings(**BASE, **ALL_FOUR)

        rendered = repr(settings)

        assert "super-secret-value" not in rendered
        assert "access-key-id" not in rendered

    def test_the_secret_is_still_retrievable_deliberately(self) -> None:
        """Masking must not make the value unusable by the factory."""
        settings = Settings(**BASE, **ALL_FOUR)

        assert settings.r2_secret_access_key is not None
        assert settings.r2_secret_access_key.get_secret_value() == "super-secret-value"


class TestStartupRequiresStorage:
    """STEP-28: a *deployment* may no longer omit object storage.

    Asserted against `get_settings()` rather than `Settings`, because that is
    where the requirement lives and where a real process meets it.
    """

    @pytest.fixture(autouse=True)
    def startup_environment(self, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
        """Supply everything except storage, and keep the cache from leaking.

        `get_settings()` is `lru_cache`d, so a result computed here would
        otherwise be served to every later test in the session — including ones
        that expect the developer's real configuration. Cleared on the way in as
        well as out, since a previous test may already have populated it.

        Storage is *not* set here: the R2 variables are removed by this module's
        other autouse fixture, which is precisely the state under test.
        """
        get_settings.cache_clear()

        monkeypatch.setenv("PROJECTONE_ENVIRONMENT", "development")
        monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
        monkeypatch.setenv("SUPABASE_SECRET_KEY", "service-key")
        monkeypatch.setenv("DATABASE_URL", "postgresql://postgres@localhost/db")
        monkeypatch.setenv("REQUEST_DATABASE_URL", "postgresql://authenticator@localhost/db")
        monkeypatch.setenv("PROJECTONE_BYOK_ENCRYPTION_KEY", TEST_BYOK_KEY)

        yield

        get_settings.cache_clear()

    def test_startup_fails_without_storage_configuration(self) -> None:
        """The proof STEP-28 Task 1 exists to produce.

        Every other required value is present, so a failure here can only be the
        storage check — not an incidentally broken environment.
        """
        with pytest.raises(SystemExit):
            get_settings()

    def test_the_exit_message_names_every_missing_variable(self) -> None:
        """An operator must learn which four variables to set.

        `SystemExit` carries the message as its argument, which is what reaches
        the container log an operator is actually reading.
        """
        with pytest.raises(SystemExit) as raised:
            get_settings()

        message = str(raised.value)
        for variable in STARTUP_REQUIRED_STORAGE_VARIABLES:
            assert variable in message, f"{variable} is required but not named in the exit message"

    def test_the_exit_message_carries_no_credential_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A partial configuration must not echo the values that *were* set.

        The startup path is exactly where a secret reaches a log (CLAUDE.md §16,
        §25). Two of the four variables are credentials, so the message names
        what is absent and never what is present.
        """
        monkeypatch.setenv("PROJECTONE_R2_ACCOUNT_ID", "real-account-id")
        monkeypatch.setenv("PROJECTONE_R2_BUCKET", "real-bucket")
        monkeypatch.setenv("PROJECTONE_R2_ACCESS_KEY_ID", "real-access-key-id")

        with pytest.raises(SystemExit) as raised:
            get_settings()

        message = str(raised.value)

        assert "real-access-key-id" not in message
        assert "real-account-id" not in message
        # The operator still learns the one thing they have to fix.
        assert "PROJECTONE_R2_SECRET_ACCESS_KEY" in message

    def test_startup_succeeds_once_all_four_are_present(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The check must gate on absence only, not reject a valid deployment.

        Without this, a check that always exited would pass every assertion
        above while making the API unstartable.
        """
        monkeypatch.setenv("PROJECTONE_R2_ACCOUNT_ID", "account-id")
        monkeypatch.setenv("PROJECTONE_R2_BUCKET", "projectone-assets")
        monkeypatch.setenv("PROJECTONE_R2_ACCESS_KEY_ID", "access-key-id")
        monkeypatch.setenv("PROJECTONE_R2_SECRET_ACCESS_KEY", "secret-value")

        settings = get_settings()

        assert settings.storage_is_configured is True
