"""Contract properties of the settings surface that need no database (STEP-19).

Three kinds of check live here, and each one guards against a defect that a
functional test would not catch:

1. **The schema refuses what it must refuse.** Asserted against the model
   directly, so the rule is proven where it is stated rather than only through
   whichever route happens to use it today.
2. **The provider literal matches the live registry.** `ProviderName` is a
   hand-written pattern for a good reason (importing the registry into a schema
   module would construct HTTP clients on every schema import), and a
   hand-written literal drifts unless something asserts it.
3. **Every write route actually carries its authorization dependency.** Read off
   the built application's route table -- a dependency dropped from a route is
   not a syntax error, it is an unguarded write path, and STEP-12a found exactly
   this shape of defect by writing the check rather than by running the suite.
"""

from decimal import Decimal

import pytest
from pydantic import TypeAdapter, ValidationError

from app.core.config import Environment, Settings
from app.core.dependencies import get_ai_providers
from app.main import create_app
from app.repositories.provider_credentials import CredentialSummary
from app.schemas.ai import (
    BudgetUpdateRequest,
    ProviderCredentialRequest,
    ProviderCredentialResponse,
    ProviderName,
)
from app.schemas.settings import ProfileUpdateRequest

# ---------------------------------------------------------------------------
# The response type structurally cannot carry a key
# ---------------------------------------------------------------------------


def test_the_credential_response_mirrors_the_summary_exactly() -> None:
    """The response model may not gain a field the summary does not have.

    `CredentialSummary` deliberately has no field capable of holding a key, so
    mirroring it is what makes a leak structurally impossible rather than
    remembered. A field added to the response "for the UI" would have to be
    populated from somewhere, and the only columns available are the excluded
    ones.
    """
    summary_fields = set(CredentialSummary.__dataclass_fields__)
    response_fields = set(ProviderCredentialResponse.model_fields)

    assert response_fields == summary_fields


def test_no_field_on_the_credential_response_is_named_like_a_key() -> None:
    """A second, independent reading of the same property.

    The mirror test above passes if *both* types gain a key field. This one does
    not, and it is cheap enough to keep as the belt to that braces.
    """
    forbidden = ("key", "secret", "token", "credential")

    for name in ProviderCredentialResponse.model_fields:
        assert not any(word in name.lower() for word in forbidden), name


# ---------------------------------------------------------------------------
# The budget request refuses spent_usd
# ---------------------------------------------------------------------------


def test_the_budget_request_refuses_spent_usd() -> None:
    """Rejected, not discarded.

    `extra="forbid"` is what makes the refusal observable. Without it a caller
    sending `spent_usd` gets a 200 and no effect, which is indistinguishable from
    success -- and STEP-18 recorded exactly this field as the one an owner must
    never be able to write.
    """
    with pytest.raises(ValidationError):
        BudgetUpdateRequest(limit_usd=Decimal("10"), spent_usd=Decimal(0))  # type: ignore[call-arg]


def test_the_budget_request_refuses_the_breaker_fields() -> None:
    """Clearing one's own tripped breaker would defeat the control entirely.

    A spend breaker trips because something spent more than expected. Resetting
    it is deliberately a manual decision made outside the tenant's own settings
    screen (`AISpendRepository.reset_breaker`), so the request schema must not be
    a path to it.
    """
    for field in ("breaker_tripped_at", "breaker_reason"):
        with pytest.raises(ValidationError):
            BudgetUpdateRequest.model_validate({"limit_usd": "10", field: None})


def test_a_zero_or_negative_ceiling_is_refused() -> None:
    """A zero ceiling refuses every call, which nobody setting a limit means.

    Disabling AI entirely is what the shutdown switch is for; conflating the two
    would make an incident control indistinguishable from a typo.
    """
    for value in ("0", "-5"):
        with pytest.raises(ValidationError):
            BudgetUpdateRequest(limit_usd=Decimal(value))


def test_a_ceiling_is_accepted_as_a_decimal_string_without_rounding() -> None:
    """The permission half, and the reason the type is `Decimal`.

    A ceiling that arrives a fraction of a cent away from what the user typed is
    a ceiling that will eventually be breached by that fraction.
    """
    request = BudgetUpdateRequest.model_validate({"limit_usd": "0.10"})

    assert request.limit_usd == Decimal("0.10")


def test_a_period_outside_its_bounds_is_refused() -> None:
    for days in (0, 366):
        with pytest.raises(ValidationError):
            BudgetUpdateRequest(limit_usd=Decimal("10"), period_days=days)


# ---------------------------------------------------------------------------
# Key and name validation
# ---------------------------------------------------------------------------


def test_a_pasted_key_is_stripped_before_its_length_is_checked() -> None:
    """A trailing newline from a paste must not be stored with the key.

    Stored with one, the key would be rejected by the provider later -- a failure
    that surfaces far from the paste that caused it.
    """
    request = ProviderCredentialRequest(api_key="  sk-a-valid-looking-key-value  \n")

    assert request.api_key == "sk-a-valid-looking-key-value"


def test_a_whitespace_only_display_name_is_refused() -> None:
    """Stripped before the bound is applied, so a blank name cannot be stored."""
    with pytest.raises(ValidationError):
        ProfileUpdateRequest(display_name="   ")


def test_the_profile_request_carries_no_identity_field() -> None:
    """Identity comes from the verified token, never from a body.

    A `user_id` or `email` field here would be an impersonation parameter. The
    `users_update_self` policy would refuse it, but by matching zero rows -- a
    404 where a 403 belongs.
    """
    assert set(ProfileUpdateRequest.model_fields) == {"display_name"}


# ---------------------------------------------------------------------------
# The provider literal matches the registry
# ---------------------------------------------------------------------------


def test_provider_names_match_the_registry() -> None:
    """The literal in `app.schemas.ai` must accept exactly the live providers.

    `ProviderName` is a hand-written pattern deliberately -- deriving it from
    `get_ai_providers()` would construct live adapter instances holding HTTP
    clients on every schema import. This is what keeps the literal honest: adding
    a provider without extending the pattern makes it unconfigurable, and the
    failure would otherwise appear as a 422 nobody could explain.
    """
    settings = Settings(
        environment=Environment.DEVELOPMENT,
        SUPABASE_URL="https://project.test",
        SUPABASE_SECRET_KEY="unused",
        DATABASE_URL="postgresql://unused/db",
        REQUEST_DATABASE_URL="postgresql://unused/db",
        byok_encryption_key="dGVzdC1ieW9rLWtleS0zMi1ieXRlcy1sb25nLXh4eHg=",
        _env_file=None,
    )

    registry = {provider.name for provider in get_ai_providers(settings)}

    # Exercised through the type rather than by re-reading its pattern, so the
    # test asserts the behaviour a request actually meets. A registered provider
    # the pattern rejects is unconfigurable; an accepted name with no adapter
    # behind it stores a credential that can never be used.
    validator = TypeAdapter(ProviderName)

    for name in registry:
        validator.validate_python(name)

    with pytest.raises(ValidationError):
        validator.validate_python("not-a-registered-provider")

    # The other direction, which is the one that actually leaks. A pattern
    # accepting a name with no adapter behind it stores a credential the router
    # can never use -- the settings screen shows the provider as configured and
    # the failure surfaces only at the first AI call. Enumerating candidates is
    # not possible from a regex, so this asserts against the known set instead,
    # and the loop above is what keeps that set from going stale.
    assert registry == {"openai", "anthropic"}


# ---------------------------------------------------------------------------
# Every write route carries its authorization dependency
# ---------------------------------------------------------------------------

#: Write routes added by STEP-19 and the permission each must require.
#:
#: Asserted against the built route table rather than trusted, because a
#: dependency dropped from a route declaration is not a syntax error -- it is a
#: write path with no gate, and it looks perfectly ordinary in review. STEP-12a
#: found exactly this shape of defect (a limiter applied to no production route)
#: by writing the check rather than by running the suite.
_GUARDED_WRITES = (
    ("PUT", "/api/v1/workspaces/{workspace_id}/ai/providers/{provider}"),
    ("DELETE", "/api/v1/workspaces/{workspace_id}/ai/providers/{provider}"),
    ("PUT", "/api/v1/workspaces/{workspace_id}/ai/budgets"),
)


@pytest.mark.parametrize(("method", "path"), _GUARDED_WRITES)
def test_every_settings_write_route_requires_a_permission(method: str, path: str) -> None:
    """Each write route resolves a `requires(...)` dependency.

    Identified by the dependency function's own module and name rather than by
    inspecting its closure: `requires` returns a locally-defined `dependency`,
    so the closure's captured permission is not reachable without relying on
    CPython internals. What matters here is that *a* permission gate is present
    -- which permission it is, is proven by the role tests in
    `test_ai_settings_endpoints.py`, through real HTTP.
    """
    app = create_app()

    matching = [
        route
        for route in app.routes
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set())
    ]

    assert matching, f"{method} {path} is not registered"

    dependant = matching[0].dependant  # type: ignore[attr-defined]
    names = {
        dependency.call.__qualname__
        for dependency in dependant.dependencies
        if dependency.call is not None
    }

    assert any("requires." in name for name in names), (
        f"{method} {path} has no requires(...) dependency: {names}"
    )


def test_the_spend_read_route_cannot_open_its_own_connection() -> None:
    """`read_records_for_workspace` takes a connection rather than opening one.

    That signature is the defence: a route holding this function cannot
    accidentally run it privileged, because there is no DSN in reach. Asserted
    rather than assumed, since a later refactor giving it a `Settings` parameter
    would silently remove the protection.
    """
    import inspect  # noqa: PLC0415 - used once, in one test

    from app.repositories.ai_spend import AISpendRepository  # noqa: PLC0415

    signature = inspect.signature(AISpendRepository.read_records_for_workspace)

    assert "connection" in signature.parameters
    assert "settings" not in signature.parameters
