"""The OpenAI provider adapter.

Speaks OpenAI's Chat Completions wire format and translates its failures into
the `ProviderError` hierarchy. Nothing above this module knows that OpenAI uses
`choices[0].message.content` or that it signals throttling with a 429.

**Written against the HTTP API rather than the `openai` SDK.** `httpx` is
already a runtime dependency (STEP-10, for Supabase Auth), so this adds nothing
to the dependency surface, while each vendor SDK would add one -- plus its
transitive tree, its own retry logic fighting the router's ceiling, and its own
release cadence. The wire format for a chat completion is a POST with three
fields; an SDK earns its keep on breadth this abstraction deliberately does not
have (CLAUDE.md §28 -- prefer existing capabilities over a new library).
"""

from __future__ import annotations

from typing import Any

import httpx

from app.ai.errors import (
    ProviderAuthenticationError,
    ProviderRateLimitedError,
    ProviderRequestError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.ai.provider import (
    AIProvider,
    Capability,
    CompletionRequest,
    CompletionResponse,
    TokenUsage,
)

#: The provider's stable identifier. A wire value: it keys BYOK rows and appears
#: in logs, so renaming it orphans stored keys.
PROVIDER_NAME = "openai"

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_BASE_URL = "https://api.openai.com/v1"

#: Indicative blended USD cost per 1k tokens, for selection's cost comparison.
#: Not billing input -- real spend reads `TokenUsage` off the response, and
#: enforcement is STEP-18's.
COST_PER_1K_TOKENS = 0.0006


class OpenAIProvider(AIProvider):
    """OpenAI, behind the common provider contract."""

    def __init__(
        self,
        timeout_seconds: float = 30.0,
        base_url: str = DEFAULT_BASE_URL,
        default_model: str = DEFAULT_MODEL,
    ) -> None:
        """Configure the adapter.

        Args:
            timeout_seconds: Per-attempt timeout. Bounded so one hanging call
                cannot hold a worker open indefinitely -- the same reasoning as
                `database_health_timeout_seconds`.
            base_url: API root. Injectable so tests point at a local transport
                and so an Azure-hosted or proxied deployment needs no new class.
            default_model: Used when the request names none.
        """
        self._timeout_seconds = timeout_seconds
        self._base_url = base_url.rstrip("/")
        self._default_model = default_model

    @property
    def name(self) -> str:
        """Return the provider's stable identifier."""
        return PROVIDER_NAME

    @property
    def capabilities(self) -> frozenset[Capability]:
        """Return what this provider can do."""
        return frozenset({Capability.CHAT_COMPLETION})

    @property
    def cost_per_1k_tokens(self) -> float:
        """Return the indicative cost used by selection."""
        return COST_PER_1K_TOKENS

    def complete(self, request: CompletionRequest, api_key: str) -> CompletionResponse:
        """Perform one chat completion against OpenAI.

        Exactly one attempt, per the interface contract. Retries and fallback
        belong to the router (CLAUDE.md §15a).
        """
        model = request.model or self._default_model
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": message.role.value, "content": message.content}
                for message in request.messages
            ],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }

        try:
            response = httpx.post(
                f"{self._base_url}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self._timeout_seconds,
            )
        except httpx.TimeoutException as error:
            raise ProviderTimeoutError(f"OpenAI timed out: {error}", PROVIDER_NAME) from error
        except httpx.HTTPError as error:
            # Connection refused, DNS failure, TLS error. Retryable: the next
            # attempt may land on a healthy edge node.
            raise ProviderUnavailableError(
                f"OpenAI is unreachable: {error}", PROVIDER_NAME
            ) from error

        _raise_for_status(response)

        return _parse_completion(response, model)


def _raise_for_status(response: httpx.Response) -> None:
    """Translate an error status into the typed hierarchy.

    Ordered by specificity, and the ordering is load-bearing: 429 must be
    checked before the generic 4xx branch, or a rate limit would be classified
    terminal and never retried.

    **The response body is never included in the raised message.** OpenAI echoes
    request content back in some errors, and request content is the user's
    prompt -- reflecting it into an error that may reach a log or a support
    ticket is a disclosure (CLAUDE.md §16, §24).
    """
    status = response.status_code

    if status < 400:
        return

    if status in (401, 403):
        raise ProviderAuthenticationError(
            f"OpenAI rejected the API key (HTTP {status})", PROVIDER_NAME
        )

    if status == 429:
        raise ProviderRateLimitedError(
            f"OpenAI rate limited this workspace (HTTP {status})", PROVIDER_NAME
        )

    if status >= 500:
        raise ProviderUnavailableError(f"OpenAI returned HTTP {status}", PROVIDER_NAME)

    raise ProviderRequestError(f"OpenAI rejected the request (HTTP {status})", PROVIDER_NAME)


def _parse_completion(response: httpx.Response, model: str) -> CompletionResponse:
    """Read a completion out of a successful response.

    A 200 carrying an unreadable body is treated as `ProviderRequestError`
    rather than allowed to raise `KeyError` or `IndexError`. An unhandled
    exception here would leave through the generic 500 handler, telling the
    caller nothing and skipping the fallback that a typed provider error
    triggers (CLAUDE.md §24).
    """
    try:
        body = response.json()
        choices = body["choices"]
        content = choices[0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as error:
        raise ProviderRequestError(
            f"OpenAI returned an unreadable response: {type(error).__name__}", PROVIDER_NAME
        ) from error

    usage_body = body.get("usage") or {}

    return CompletionResponse(
        content=content,
        provider=PROVIDER_NAME,
        model=body.get("model", model),
        usage=TokenUsage(
            prompt_tokens=usage_body.get("prompt_tokens", 0),
            completion_tokens=usage_body.get("completion_tokens", 0),
        ),
    )
