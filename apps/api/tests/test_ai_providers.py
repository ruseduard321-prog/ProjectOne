"""One suite, run against every provider.

STEP-17's Validation requires that "both providers satisfy the interface, proven
by the same test suite running against each rather than by two bespoke suites."
That is what `@pytest.mark.parametrize` over `PROVIDER_CASES` does here: adding a
third provider means adding one entry, and every contract test below runs
against it immediately.

Two bespoke suites would pass forever while the abstraction rotted -- each
asserting its own provider's behaviour, neither asserting they agree. The whole
value of an interface is the agreement.

Network is never touched. `httpx.post` is substituted per test, which also means
these tests assert what was *sent* on the wire, not merely what came back.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
import pytest

from app.ai.errors import (
    ProviderAuthenticationError,
    ProviderRateLimitedError,
    ProviderRequestError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.ai.provider import AIProvider, Capability, CompletionRequest, Message, Role
from app.ai.providers.anthropic import AnthropicProvider
from app.ai.providers.openai import OpenAIProvider


@dataclass
class ProviderCase:
    """A provider plus the wire shapes its vendor actually uses."""

    name: str
    build: Any
    success_body: dict[str, Any]
    expected_text: str
    expected_prompt_tokens: int
    expected_completion_tokens: int


PROVIDER_CASES = [
    ProviderCase(
        name="openai",
        build=OpenAIProvider,
        success_body={
            "model": "gpt-4o-mini",
            "choices": [{"message": {"role": "assistant", "content": "Hello from OpenAI"}}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 5},
        },
        expected_text="Hello from OpenAI",
        expected_prompt_tokens=11,
        expected_completion_tokens=5,
    ),
    ProviderCase(
        name="anthropic",
        build=AnthropicProvider,
        success_body={
            "model": "claude-haiku-4-5-20251001",
            "content": [{"type": "text", "text": "Hello from Anthropic"}],
            "usage": {"input_tokens": 11, "output_tokens": 5},
        },
        expected_text="Hello from Anthropic",
        expected_prompt_tokens=11,
        expected_completion_tokens=5,
    ),
]

CASE_IDS = [case.name for case in PROVIDER_CASES]

API_KEY = "sk-test-abcdefghijklmnop"  # noqa: S105 - fake key for a substituted transport


def a_request(**overrides: Any) -> CompletionRequest:
    """Build a completion request with sensible defaults."""
    defaults: dict[str, Any] = {
        "messages": (Message(role=Role.USER, content="Hi"),),
    }
    defaults.update(overrides)

    return CompletionRequest(**defaults)


def respond_with(
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
    body: dict[str, Any] | None = None,
    capture: dict[str, Any] | None = None,
) -> None:
    """Substitute `httpx.post` with one returning a fixed response."""

    def fake_post(url: str, **kwargs: Any) -> httpx.Response:
        if capture is not None:
            capture["url"] = url
            capture.update(kwargs)

        return httpx.Response(
            status_code=status_code,
            json=body if body is not None else {},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)


def raise_on_post(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    """Substitute `httpx.post` with one that raises."""

    def fake_post(url: str, **kwargs: Any) -> httpx.Response:
        raise error

    monkeypatch.setattr(httpx, "post", fake_post)


@pytest.mark.parametrize("case", PROVIDER_CASES, ids=CASE_IDS)
class TestEveryProviderSatisfiesTheContract:
    """The contract tests. Every provider must pass all of these."""

    def test_it_reports_a_stable_name(self, case: ProviderCase) -> None:
        provider: AIProvider = case.build()

        assert provider.name == case.name

    def test_it_declares_chat_completion(self, case: ProviderCase) -> None:
        provider: AIProvider = case.build()

        assert Capability.CHAT_COMPLETION in provider.capabilities

    def test_it_reports_a_positive_cost(self, case: ProviderCase) -> None:
        # Selection sorts on this. A zero or negative cost would always win,
        # which would make the cost stage meaningless rather than merely wrong.
        provider: AIProvider = case.build()

        assert provider.cost_per_1k_tokens > 0

    def test_a_successful_call_returns_the_text(
        self, case: ProviderCase, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        respond_with(monkeypatch, 200, case.success_body)
        provider: AIProvider = case.build()

        response = provider.complete(a_request(), API_KEY)

        assert response.content == case.expected_text

    def test_the_response_names_the_provider_that_answered(
        self, case: ProviderCase, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # After a fallback the caller's request named one provider and another
        # answered. A response that cannot say which is one the caller cannot
        # honestly attribute (CLAUDE.md §15).
        respond_with(monkeypatch, 200, case.success_body)
        provider: AIProvider = case.build()

        response = provider.complete(a_request(), API_KEY)

        assert response.provider == case.name

    def test_token_usage_is_normalised_across_vendors(
        self, case: ProviderCase, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # OpenAI says prompt_tokens/completion_tokens; Anthropic says
        # input_tokens/output_tokens. Both must arrive as the same fields, or
        # STEP-18 would need per-provider accounting code.
        respond_with(monkeypatch, 200, case.success_body)
        provider: AIProvider = case.build()

        response = provider.complete(a_request(), API_KEY)

        assert response.usage.prompt_tokens == case.expected_prompt_tokens
        assert response.usage.completion_tokens == case.expected_completion_tokens
        assert response.usage.total_tokens == (
            case.expected_prompt_tokens + case.expected_completion_tokens
        )

    def test_a_rejected_key_is_terminal(
        self, case: ProviderCase, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        respond_with(monkeypatch, 401)
        provider: AIProvider = case.build()

        with pytest.raises(ProviderAuthenticationError):
            provider.complete(a_request(), API_KEY)

    def test_throttling_is_retryable_not_terminal(
        self, case: ProviderCase, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The ordering constraint in `_raise_for_status`: 429 is a 4xx, so a
        # naive "4xx is terminal" check would classify it wrong and never retry
        # a condition that is purely temporal.
        respond_with(monkeypatch, 429)
        provider: AIProvider = case.build()

        with pytest.raises(ProviderRateLimitedError):
            provider.complete(a_request(), API_KEY)

    def test_a_server_error_is_retryable(
        self, case: ProviderCase, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        respond_with(monkeypatch, 503)
        provider: AIProvider = case.build()

        with pytest.raises(ProviderUnavailableError):
            provider.complete(a_request(), API_KEY)

    def test_a_malformed_request_is_terminal(
        self, case: ProviderCase, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        respond_with(monkeypatch, 400)
        provider: AIProvider = case.build()

        with pytest.raises(ProviderRequestError):
            provider.complete(a_request(), API_KEY)

    def test_a_timeout_is_retryable(
        self, case: ProviderCase, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        raise_on_post(monkeypatch, httpx.ReadTimeout("too slow"))
        provider: AIProvider = case.build()

        with pytest.raises(ProviderTimeoutError):
            provider.complete(a_request(), API_KEY)

    def test_an_unreachable_host_is_retryable(
        self, case: ProviderCase, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        raise_on_post(monkeypatch, httpx.ConnectError("no route"))
        provider: AIProvider = case.build()

        with pytest.raises(ProviderUnavailableError):
            provider.complete(a_request(), API_KEY)

    def test_an_unreadable_body_does_not_escape_as_a_raw_exception(
        self, case: ProviderCase, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A 200 whose shape is unexpected must still leave as a ProviderError.
        # A raw KeyError would bypass the router's fallback entirely and
        # surface as a 500 (CLAUDE.md §24).
        respond_with(monkeypatch, 200, {"unexpected": "shape"})
        provider: AIProvider = case.build()

        with pytest.raises(ProviderRequestError):
            provider.complete(a_request(), API_KEY)

    def test_the_key_is_sent_but_never_placed_in_the_error_message(
        self, case: ProviderCase, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The credential must reach the vendor and must not reach an exception
        # message, which is the value most likely to be logged verbatim.
        respond_with(monkeypatch, 401)
        provider: AIProvider = case.build()

        with pytest.raises(ProviderAuthenticationError) as raised:
            provider.complete(a_request(), API_KEY)

        assert API_KEY not in str(raised.value)

    def test_the_request_body_is_not_echoed_into_an_error(
        self, case: ProviderCase, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Vendors echo request content in some errors, and request content is
        # the user's prompt. It must not reach an error that lands in a log.
        secret_prompt = "my confidential business plan"
        respond_with(monkeypatch, 400, {"error": {"message": secret_prompt}})
        provider: AIProvider = case.build()

        with pytest.raises(ProviderRequestError) as raised:
            provider.complete(
                a_request(messages=(Message(role=Role.USER, content=secret_prompt),)),
                API_KEY,
            )

        assert secret_prompt not in str(raised.value)

    def test_exactly_one_upstream_call_is_made(
        self, case: ProviderCase, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The interface contract says one attempt. A provider retrying
        # internally would multiply the router's ceiling by its own count, and
        # the real spend limit would be a product nobody wrote down
        # (CLAUDE.md §15a).
        calls = 0

        def counting_post(url: str, **kwargs: Any) -> httpx.Response:
            nonlocal calls
            calls += 1
            raise httpx.ConnectError("no route")

        monkeypatch.setattr(httpx, "post", counting_post)
        provider: AIProvider = case.build()

        with pytest.raises(ProviderUnavailableError):
            provider.complete(a_request(), API_KEY)

        assert calls == 1


class TestVendorSpecificTranslation:
    """Where the two vendors genuinely differ, and the adapter must absorb it."""

    def test_openai_sends_the_key_as_a_bearer_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        capture: dict[str, Any] = {}
        respond_with(monkeypatch, 200, PROVIDER_CASES[0].success_body, capture)

        OpenAIProvider().complete(a_request(), API_KEY)

        assert capture["headers"]["Authorization"] == f"Bearer {API_KEY}"

    def test_anthropic_sends_the_key_in_x_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        capture: dict[str, Any] = {}
        respond_with(monkeypatch, 200, PROVIDER_CASES[1].success_body, capture)

        AnthropicProvider().complete(a_request(), API_KEY)

        assert capture["headers"]["x-api-key"] == API_KEY
        assert "Authorization" not in capture["headers"]

    def test_openai_keeps_the_system_prompt_in_messages(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        capture: dict[str, Any] = {}
        respond_with(monkeypatch, 200, PROVIDER_CASES[0].success_body, capture)

        OpenAIProvider().complete(
            a_request(
                messages=(
                    Message(role=Role.SYSTEM, content="Be terse"),
                    Message(role=Role.USER, content="Hi"),
                )
            ),
            API_KEY,
        )

        assert capture["json"]["messages"][0] == {"role": "system", "content": "Be terse"}
        assert "system" not in capture["json"]

    def test_anthropic_lifts_the_system_prompt_out_of_messages(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The concrete reason this abstraction earns its keep: Anthropic rejects
        # a `system` role inside `messages`, so the identical CompletionRequest
        # must be reshaped here rather than by the caller.
        capture: dict[str, Any] = {}
        respond_with(monkeypatch, 200, PROVIDER_CASES[1].success_body, capture)

        AnthropicProvider().complete(
            a_request(
                messages=(
                    Message(role=Role.SYSTEM, content="Be terse"),
                    Message(role=Role.USER, content="Hi"),
                )
            ),
            API_KEY,
        )

        assert capture["json"]["system"] == "Be terse"
        assert all(m["role"] != "system" for m in capture["json"]["messages"])

    def test_anthropic_joins_multiple_system_messages_rather_than_dropping_them(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Silently keeping only the last would change what the model was told
        # based purely on which provider served the request.
        capture: dict[str, Any] = {}
        respond_with(monkeypatch, 200, PROVIDER_CASES[1].success_body, capture)

        AnthropicProvider().complete(
            a_request(
                messages=(
                    Message(role=Role.SYSTEM, content="Be terse"),
                    Message(role=Role.SYSTEM, content="Be formal"),
                    Message(role=Role.USER, content="Hi"),
                )
            ),
            API_KEY,
        )

        assert "Be terse" in capture["json"]["system"]
        assert "Be formal" in capture["json"]["system"]

    def test_anthropic_joins_only_text_blocks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # A future tool-use block must not be stringified into the user's answer.
        respond_with(
            monkeypatch,
            200,
            {
                "model": "claude-haiku-4-5-20251001",
                "content": [
                    {"type": "text", "text": "The answer is "},
                    {"type": "tool_use", "id": "t1", "name": "calc", "input": {}},
                    {"type": "text", "text": "42"},
                ],
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )

        response = AnthropicProvider().complete(a_request(), API_KEY)

        assert response.content == "The answer is 42"

    def test_anthropic_pins_its_api_version(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # An API version that drifts changes behaviour with no deploy, which is
        # the opposite of the determinism CLAUDE.md §15 requires.
        capture: dict[str, Any] = {}
        respond_with(monkeypatch, 200, PROVIDER_CASES[1].success_body, capture)

        AnthropicProvider().complete(a_request(), API_KEY)

        assert capture["headers"]["anthropic-version"] == "2023-06-01"

    def test_a_request_is_not_mutated_by_being_sent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # After a fallback the *same* request object goes to the second
        # provider. If the first had mutated it, the bug would appear only when
        # the primary fails -- when it is hardest to diagnose.
        respond_with(monkeypatch, 200, PROVIDER_CASES[1].success_body)
        request = a_request(
            messages=(
                Message(role=Role.SYSTEM, content="Be terse"),
                Message(role=Role.USER, content="Hi"),
            )
        )

        AnthropicProvider().complete(request, API_KEY)

        assert len(request.messages) == 2
        assert request.messages[0].role is Role.SYSTEM
