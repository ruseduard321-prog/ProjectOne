"""All-or-none validation of the R2 storage configuration.

Zero configured values is valid — STEP-27 ships the abstraction before any
caller exists, so a deployment that never touches storage must still start. Four
is valid. **One, two or three is a deployment mistake**, and the point of these
tests is that it is caught at startup rather than surfacing much later as a
misleading "storage is not configured" on the first upload.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.core.config import Settings, _error_location


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
    """The two states a deployment is allowed to be in."""

    def test_no_storage_configuration_is_valid(self) -> None:
        """STEP-27 has no caller, so storage may be entirely unconfigured."""
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
