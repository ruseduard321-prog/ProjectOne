"""The Anthropic provider adapter.

The second implementation, and the one that proves the interface is an
abstraction rather than OpenAI's shape with a different name on it. Anthropic's
Messages API differs from Chat Completions in four ways that all had to be
absorbed *here* rather than leaked upward:

| | OpenAI | Anthropic |
|---|---|---|
| Credential header | `Authorization: Bearer` | `x-api-key` |
| System prompt | A message with `role: system` | A **top-level `system` field** |
| Response text | `choices[0].message.content` | `content[0].text` |
| Token usage | `prompt_tokens` / `completion_tokens` | `input_tokens` / `output_tokens` |

The system-prompt difference is the interesting one. Anthropic rejects a
`system` role inside `messages`, so a request built naturally for OpenAI is
*invalid* here -- and the router must be able to hand the identical
`CompletionRequest` to either. `_split_system` is where that reconciliation
happens, and it is the concrete reason this interface earns its keep.
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
    Message,
    Role,
    TokenUsage,
)

#: The provider's stable identifier. A wire value -- see the OpenAI adapter.
PROVIDER_NAME = "anthropic"

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_BASE_URL = "https://api.anthropic.com/v1"

#: Required by the Messages API and pinned rather than tracking "latest": an
#: API version that changes underneath a deployment changes behaviour without a
#: deploy, which is the opposite of the determinism CLAUDE.md §15 requires.
API_VERSION = "2023-06-01"

#: Indicative blended USD cost per 1k tokens, for selection's cost comparison.
COST_PER_1K_TOKENS = 0.0008


class AnthropicProvider(AIProvider):
    """Anthropic, behind the common provider contract."""

    def __init__(
        self,
        timeout_seconds: float = 30.0,
        base_url: str = DEFAULT_BASE_URL,
        default_model: str = DEFAULT_MODEL,
    ) -> None:
        """Configure the adapter.

        Args:
            timeout_seconds: Per-attempt timeout, bounded so a hanging call
                cannot hold a worker open.
            base_url: API root, injectable for tests and proxied deployments.
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
        """Perform one chat completion against Anthropic.

        Exactly one attempt, per the interface contract.
        """
        model = request.model or self._default_model
        system_prompt, conversation = _split_system(request.messages)

        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": message.role.value, "content": message.content} for message in conversation
            ],
            # Required by the Messages API, unlike OpenAI where it is optional.
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }

        # Omitted entirely rather than sent as null: the API rejects an explicit
        # null for this field.
        if system_prompt is not None:
            payload["system"] = system_prompt

        try:
            response = httpx.post(
                f"{self._base_url}/messages",
                json=payload,
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": API_VERSION,
                    "Content-Type": "application/json",
                },
                timeout=self._timeout_seconds,
            )
        except httpx.TimeoutException as error:
            raise ProviderTimeoutError(f"Anthropic timed out: {error}", PROVIDER_NAME) from error
        except httpx.HTTPError as error:
            raise ProviderUnavailableError(
                f"Anthropic is unreachable: {error}", PROVIDER_NAME
            ) from error

        _raise_for_status(response)

        return _parse_completion(response, model)


def _split_system(messages: tuple[Message, ...]) -> tuple[str | None, tuple[Message, ...]]:
    """Separate system content from the conversation.

    Anthropic takes the system prompt as a top-level field and **rejects** a
    `system` role inside `messages`, so this conversion is required rather than
    stylistic.

    Multiple system messages are joined with blank lines rather than the last
    one winning. Silently discarding earlier system content would change what
    the model was told based purely on which provider served the request --
    exactly the kind of provider-dependent behaviour this abstraction exists to
    prevent.

    Returns:
        The joined system prompt (None when there was none), and the remaining
        messages in their original order.
    """
    system_parts = [m.content for m in messages if m.role is Role.SYSTEM]
    conversation = tuple(m for m in messages if m.role is not Role.SYSTEM)

    if not system_parts:
        return None, conversation

    return "\n\n".join(system_parts), conversation


def _raise_for_status(response: httpx.Response) -> None:
    """Translate an error status into the typed hierarchy.

    Same ordering constraint as the OpenAI adapter: 429 before the generic 4xx
    branch, or throttling would be misclassified as terminal.

    The response body is deliberately excluded from the message -- it can echo
    request content, which is the user's prompt.
    """
    status = response.status_code

    if status < 400:
        return

    if status in (401, 403):
        raise ProviderAuthenticationError(
            f"Anthropic rejected the API key (HTTP {status})", PROVIDER_NAME
        )

    if status == 429:
        raise ProviderRateLimitedError(
            f"Anthropic rate limited this workspace (HTTP {status})", PROVIDER_NAME
        )

    # 529 is Anthropic's "overloaded" signal and is not a standard 5xx, so the
    # >= 500 comparison covers it deliberately rather than incidentally.
    if status >= 500:
        raise ProviderUnavailableError(f"Anthropic returned HTTP {status}", PROVIDER_NAME)

    raise ProviderRequestError(f"Anthropic rejected the request (HTTP {status})", PROVIDER_NAME)


def _parse_completion(response: httpx.Response, model: str) -> CompletionResponse:
    """Read a completion out of a successful response.

    Anthropic returns `content` as a list of typed blocks; only `text` blocks
    are joined. A future response containing a tool-use block would otherwise
    stringify a dict into the user's answer.
    """
    try:
        body = response.json()
        blocks = body["content"]
        content = "".join(
            block["text"] for block in blocks if isinstance(block, dict) and "text" in block
        )
    except (ValueError, KeyError, IndexError, TypeError) as error:
        raise ProviderRequestError(
            f"Anthropic returned an unreadable response: {type(error).__name__}", PROVIDER_NAME
        ) from error

    usage_body = body.get("usage") or {}

    return CompletionResponse(
        content=content,
        provider=PROVIDER_NAME,
        model=body.get("model", model),
        usage=TokenUsage(
            prompt_tokens=usage_body.get("input_tokens", 0),
            completion_tokens=usage_body.get("output_tokens", 0),
        ),
    )
