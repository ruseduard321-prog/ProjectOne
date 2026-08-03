"""What a call actually cost, in money rather than in tokens.

STEP-17 deliberately left this gap. `AIProvider.cost_per_1k_tokens` is a single
indicative scalar whose only job is to make two providers *comparable* during
selection -- it is not billing input, and using it to compute spend would be
wrong in three ways at once:

1. **It does not distinguish prompt from completion tokens**, which every major
   provider prices differently, usually by a factor of three to five.
2. **It is per provider, not per model.** Cost varies far more between a
   vendor's cheapest and most capable model than it does between vendors.
3. **It is deliberately approximate.** Selection only needs the ordering to be
   right; a budget ceiling needs the number to be right.

So this module exists, and the separation is the point: a change to selection's
cost heuristic must never silently change what a workspace is charged.

## Prices are hardcoded, and that is a stated limitation

There is no pricing API call here. Provider pricing changes rarely, a network
call on the spend path would make every AI request depend on a second upstream
service, and a *failed* pricing lookup would leave a call with no cost to charge
against -- which is a budget hole, not a degraded feature.

The trade-off is honest rather than hidden: **when a provider changes its
prices, this table is wrong until someone updates it.** `UNKNOWN_MODEL_RATE`
below is what keeps that from becoming a silent undercharge.

## An unknown model is charged, not waived

The single most dangerous behaviour this module could have is returning zero for
a model it does not recognise. A new model would then be free, uncapped, and
invisible to every ceiling -- and it would arrive precisely when someone changes
a default model name, which is a routine edit.

An unknown model is therefore charged at a **deliberately pessimistic** rate,
higher than any real model in the table. A workspace hits its ceiling early and
someone investigates; the failure mode is a support ticket rather than a bill.
"""

from __future__ import annotations

from decimal import Decimal

from app.ai.provider import TokenUsage
from app.core.logging import get_logger, log_context

logger = get_logger(__name__)

#: USD per 1,000 tokens, as (prompt, completion), keyed by exact model name.
#:
#: `Decimal`, never float. These values are multiplied and accumulated into a
#: running total that a ceiling is compared against, and binary floating point
#: accumulates error -- a ceiling compared against a drifting total is a ceiling
#: that drifts. The database column is `numeric` for the same reason.
#:
#: Keyed on the exact model string the provider reports back, not on a prefix.
#: Prefix matching would silently price `gpt-4o-mini-2099-preview` as the model
#: it happens to share characters with, which is exactly the class of quiet
#: mispricing `UNKNOWN_MODEL_RATE` exists to make loud.
MODEL_RATES: dict[str, tuple[Decimal, Decimal]] = {
    # OpenAI
    "gpt-4o-mini": (Decimal("0.00015"), Decimal("0.0006")),
    "gpt-4o": (Decimal("0.0025"), Decimal("0.01")),
    # Anthropic
    "claude-haiku-4-5-20251001": (Decimal("0.001"), Decimal("0.005")),
    "claude-sonnet-4-5-20250929": (Decimal("0.003"), Decimal("0.015")),
}

#: What an unrecognised model is charged, per 1,000 tokens, both directions.
#:
#: Higher than every rate above, deliberately. See the module docstring: the
#: alternative to overcharging an unknown model is letting it spend without a
#: ceiling, and of the two failure modes only one costs the customer money they
#: did not agree to.
UNKNOWN_MODEL_RATE = (Decimal("0.02"), Decimal("0.06"))

#: What one call is assumed to cost before it is made.
#:
#: A budget is checked *before* the call, and the real cost is unknowable until
#: after it. This is the pessimistic placeholder reserved in the meantime -- see
#: `AISpendService.reserve`. It is priced as a worst case rather than an average:
#: reserving too little would let a workspace start a call that takes it past its
#: ceiling, which is the one outcome the reservation exists to prevent.
_RESERVATION_COMPLETION_HEADROOM = Decimal("1.0")


def _rate_for(model: str) -> tuple[Decimal, Decimal]:
    """Return the (prompt, completion) rate for a model.

    An unknown model is priced pessimistically **and logged at warning**. Both
    halves matter: the price keeps the ceiling honest, and the log is what tells
    an operator that this module needs updating rather than leaving them to infer
    it from a billing discrepancy weeks later (CLAUDE.md §26).
    """
    rate = MODEL_RATES.get(model)

    if rate is None:
        logger.warning(
            log_context(
                event="ai_pricing_unknown_model",
                model=model,
                charged_at="unknown_model_rate",
            )
        )
        return UNKNOWN_MODEL_RATE

    return rate


def cost_of(model: str, usage: TokenUsage) -> Decimal:
    """Return what a completed call cost, in USD.

    Computed from the provider's own reported token counts, never estimated:
    `TokenUsage` is already normalised across vendors (STEP-17), which is why
    this needs no per-provider branching.

    Args:
        model: The model that actually served the call, as the provider
            reported it -- not the model the caller asked for, which may have
            been None.
        usage: The provider's own token accounting.

    Returns:
        The cost in USD, at `numeric(12, 6)` precision.
    """
    prompt_rate, completion_rate = _rate_for(model)

    prompt_cost = (Decimal(usage.prompt_tokens) / 1000) * prompt_rate
    completion_cost = (Decimal(usage.completion_tokens) / 1000) * completion_rate

    # Quantized to the column's scale here rather than at the database boundary,
    # so the value this function returns is exactly the value that gets stored.
    # Rounding at the edge instead would mean the reserve and the settle could
    # round differently and leave a permanent residue in the running total.
    return (prompt_cost + completion_cost).quantize(Decimal("0.000001"))


def estimated_cost_of(model: str | None, max_tokens: int, prompt_tokens: int) -> Decimal:
    """Return the pessimistic cost to reserve before a call is made.

    **This is deliberately an over-estimate.** It assumes the completion runs to
    the full `max_tokens` the caller permitted, because that is the most the call
    can possibly cost and a reservation that could be exceeded is not a
    reservation. The difference is returned to the workspace on settlement.

    Args:
        model: The model the caller requested, or None when they left the choice
            to the provider. None is priced at the unknown rate, which is
            pessimistic in the same safe direction.
        max_tokens: The caller's own ceiling on completion length.
        prompt_tokens: An estimate of the prompt size, from the request.

    Returns:
        The amount to reserve, in USD.
    """
    prompt_rate, completion_rate = _rate_for(model) if model else UNKNOWN_MODEL_RATE

    prompt_cost = (Decimal(prompt_tokens) / 1000) * prompt_rate
    completion_cost = (
        (Decimal(max_tokens) / 1000) * completion_rate * _RESERVATION_COMPLETION_HEADROOM
    )

    return (prompt_cost + completion_cost).quantize(Decimal("0.000001"))


def estimate_prompt_tokens(text: str) -> int:
    """Return a rough token count for a prompt, before any provider sees it.

    Four characters per token is the widely-used approximation for English text
    under byte-pair encodings. It is **not** accurate, and nothing downstream
    treats it as though it were: it feeds only the pre-call reservation, which is
    replaced by the provider's real count on settlement.

    A real tokenizer was considered and rejected. It would add a dependency per
    provider (CLAUDE.md §28), each with its own vocabulary files, to compute a
    number that is discarded moments later -- and would still be wrong for any
    provider whose tokenizer is not published.
    """
    return max(1, len(text) // 4)
