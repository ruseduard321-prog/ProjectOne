"""The contract every AI provider implements, and the vocabulary around it.

This module is deliberately the *only* thing the router knows about providers.
It imports no HTTP client, no vendor SDK and no FastAPI: a provider is a class
with one method, and the router depends on this abstraction rather than on any
implementation of it (CLAUDE.md §7 -- provider independence, §12 -- dependency
inversion).

## Why an abstract base class rather than a Protocol

A `Protocol` would be structurally satisfied by any object with the right
method shape, which sounds like the more decoupled choice. It is the wrong one
here: a provider that forgets `name` or returns the wrong type would be accepted
silently and fail at the moment it is first selected -- in production, on a real
user's request. An ABC fails at import, which is the only time this class of
mistake is cheap.

## What is deliberately not on this interface

Kept narrow on purpose (CLAUDE.md §29/§35 -- build for what is scheduled, not
for what might arrive):

- **No streaming.** [[STEP-23 AI Chat End to End]] owns chat's transport. Adding
  a streaming method now would mean two implementations of a contract no caller
  exercises, and a wrong guess about its shape is more expensive to unwind than
  the gap it fills.
- **No embeddings, no image generation, no tool calling.** No scheduled step
  consumes them.
- **No cost ceilings or spend accounting.** That is [[STEP-18 AI Cost Governance
  Controls]], which is a hard gate before any of this reaches a user. What lives
  here is the *cost input* to selection (`cost_per_1k_tokens`), not enforcement.

Adding a capability later is one method on this class and one implementation per
provider. Removing a speculative one is a breaking change to every provider that
implemented it.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum


class Capability(StrEnum):
    """What a provider can do.

    [[AI Providers]]' selection flow puts a **capability check** between user
    preference and availability: a preference for a provider that cannot perform
    the requested operation is not a reason to fail, it is a reason to move on.
    That check needs a vocabulary, and this is it.

    Only `CHAT_COMPLETION` exists today because it is the only operation any
    scheduled step performs. The enum exists rather than a bare boolean so
    adding the second one does not change the shape of the selection code.
    """

    CHAT_COMPLETION = "chat_completion"


class Role(StrEnum):
    """Who authored a message in a conversation.

    Deliberately provider-neutral. Every major provider uses these three names
    or maps cleanly onto them, and a provider whose wire format differs converts
    in its own adapter rather than leaking its vocabulary into this contract.
    """

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True)
class Message:
    """One turn in a conversation.

    Frozen because a request that a provider adapter could mutate is a request
    the *next* provider would receive in an altered state after a fallback --
    a class of bug that only appears once the primary fails, which is exactly
    when it is hardest to diagnose.
    """

    role: Role
    content: str


@dataclass(frozen=True)
class CompletionRequest:
    """What the caller wants, expressed without reference to any provider.

    `model` is deliberately **optional**. A caller naming a model has named a
    provider implicitly, which defeats the routing this module exists to do;
    leaving it None lets each provider apply its own default. It is kept
    available because a caller who genuinely needs a specific model (a
    reproducibility requirement, a capability only one model has) should not
    have to bypass the router to get one.
    """

    messages: tuple[Message, ...]
    model: str | None = None
    max_tokens: int = 1024
    temperature: float = 0.7

    #: The workspace this request is made on behalf of. Carried on the request
    #: rather than passed alongside it so that a BYOK key lookup and a spend
    #: record can never be attributed to a different tenant than the call
    #: itself -- they read the same field.
    workspace_id: uuid.UUID | None = None


@dataclass(frozen=True)
class TokenUsage:
    """What a call consumed.

    Reported by the provider rather than estimated by the router. An estimate
    would be a number that looks authoritative and is not, and [[STEP-18 AI Cost
    Governance Controls]] will meter real spend against these values.
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        """Return the total tokens consumed by the call."""
        return self.prompt_tokens + self.completion_tokens


@dataclass(frozen=True)
class CompletionResponse:
    """What a provider returned, plus who returned it.

    `provider` and `model` are on the response deliberately. After a fallback
    the caller's request named one provider (or none) and a different one
    answered -- a response that does not say which is a response the caller
    cannot honestly attribute (CLAUDE.md §15: AI never pretends certainty).
    """

    content: str
    provider: str
    model: str
    usage: TokenUsage = field(default_factory=TokenUsage)

    #: True when this response came from a provider other than the one
    #: selection originally chose. Surfaced rather than hidden: a silent
    #: fallback is the "confident-sounding output over a silent fallback" that
    #: CLAUDE.md §15 forbids.
    served_after_fallback: bool = False


class AIProvider(ABC):
    """One AI provider, behind a contract the router can depend on.

    Implementations live in `app/ai/providers/`. Each is responsible for its own
    wire format, its own authentication and its own error translation -- and for
    nothing else. Selection, retries, fallback and health tracking are the
    router's concerns, and an implementation that retries internally would
    silently multiply the router's own ceiling (CLAUDE.md §15a).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the stable identifier for this provider.

        Used as a dictionary key, logged on every selection decision, and stored
        against BYOK keys. It is a wire value in all but name: changing it
        orphans stored keys, so it must not be derived from a class name that
        someone might reasonably rename.
        """

    @property
    @abstractmethod
    def capabilities(self) -> frozenset[Capability]:
        """Return what this provider can do."""

    @property
    @abstractmethod
    def cost_per_1k_tokens(self) -> float:
        """Return an indicative cost, for selection's cost-evaluation stage.

        A single scalar rather than a per-model pricing table, deliberately:
        selection compares providers, and a comparison needs one comparable
        number. Real spend accounting reads `TokenUsage` from the response and
        is [[STEP-18 AI Cost Governance Controls]]' problem, not this one.

        Expressed in USD so two providers are comparable at all. A provider
        priced in another currency converts in its own adapter.
        """

    @abstractmethod
    def complete(self, request: CompletionRequest, api_key: str) -> CompletionResponse:
        """Perform one chat completion.

        **Exactly one attempt.** No retries, no fallback, no backoff -- those
        belong to the router, which owns the ceilings CLAUDE.md §15a requires. A
        provider that retried internally would multiply the router's ceiling by
        its own count, and the resulting spend limit would be the product of two
        numbers nobody wrote down.

        Args:
            request: What to generate, provider-neutrally.
            api_key: The workspace's BYOK credential for this provider. Passed
                per call rather than held on the instance so a provider object
                can be shared across tenants without ever holding one tenant's
                key where another tenant's request could reach it.

        Returns:
            The completion, attributed to this provider.

        Raises:
            ProviderError: on any failure. Implementations translate their own
                exceptions into this hierarchy so the router never needs to know
                what an `httpx.ConnectError` is.
        """
