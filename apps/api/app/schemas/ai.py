"""Request and response contracts for the AI settings endpoints.

[[STEP-19 Settings and BYOK UI]] adds the first HTTP routes that reach the AI
layer at all, so these schemas are the outermost gate on two things that were
previously unreachable: a workspace's provider keys, and the ceilings that bound
its spend.

Three properties are enforced here rather than in a route body, because a schema
is the one place a rule cannot be forgotten by the next endpoint added:

1. **No response type can carry key material.** `ProviderCredentialResponse`
   mirrors `CredentialSummary` field for field, and that dataclass deliberately
   has no field capable of holding a key (encrypted or otherwise). A future route
   returning this type cannot leak one even by accident.
2. **`spent_usd` is not an accepted input.** `BudgetUpdateRequest` accepts
   `limit_usd` and `period_interval` and nothing else, with `extra="forbid"` so
   sending it is a **422 rather than a silent no-op**. The column-level grant
   from migration `c9d3b71e08af` is the second, independent gate.
3. **Every numeric bound is stated.** A budget with no upper bound is a typo away
   from being no budget at all.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

#: Providers a workspace may store a key for.
#:
#: Constrained at the edge rather than accepted freely, so a typo produces a 422
#: naming the valid values instead of a stored credential for a provider that
#: does not exist -- which would look configured on the settings screen and fail
#: only when an AI call was finally attempted.
#:
#: Kept as a literal list rather than derived from `get_ai_providers()`: that
#: function builds live adapter instances holding HTTP clients, and importing it
#: into a schema module would make every schema import construct them.
#: `test_provider_names_match_the_registry` asserts the two agree, which is the
#: check that keeps a literal honest.
ProviderName = Annotated[str, Field(pattern=r"^(openai|anthropic)$")]

#: A provider API key as submitted.
#:
#: Whitespace-stripped before the length bound, so a pasted key with a trailing
#: newline is accepted rather than being stored with one and rejected by the
#: provider later. The upper bound is generous: key formats change, and a bound
#: that rejects a valid new-format key is discovered only by a user who cannot
#: save one.
#:
#: **Not `SecretStr`.** That type protects a value from appearing in a `repr`,
#: and this one is never repr'd -- it is read once in the route, handed to
#: `ProviderCredentialService.store`, and never held. Reaching for it here would
#: suggest the protection is stronger than it is: the real controls are that
#: this field exists on no *response* model and that the redacting log filter
#: (STEP-12) strips key-shaped values from every record.
PlaintextKey = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=8, max_length=512),
]

#: A spend ceiling in US dollars.
#:
#: `Decimal` rather than `float`, matching `ai_budgets.limit_usd` -- binary
#: floating point cannot represent 0.10 exactly, and a ceiling that is a
#: fraction of a cent away from what the user typed is a ceiling that will
#: eventually be breached by that fraction.
#:
#: `gt=0` rather than `ge=0`: a zero ceiling refuses every call, which a user
#: reaching for a spending limit almost never means. Disabling AI entirely is
#: what the shutdown switch is for, and conflating the two would make an
#: incident control indistinguishable from a typo.
LimitUsd = Annotated[Decimal, Field(gt=0, le=Decimal("1000000"), max_digits=12, decimal_places=6)]

#: How long a budget period lasts, in days.
#:
#: Days rather than a raw `timedelta`: JSON has no interval type, so a
#: `timedelta` field would accept ISO-8601 duration strings that nobody building
#: a settings form would produce. An integer count of days is what the UI has.
PeriodDays = Annotated[int, Field(ge=1, le=365)]

#: Bounds on how much spend history one request may ask for.
#:
#: The same reasoning as `AuditLimit`: an unbounded limit on an append-only table
#: is an invitation to ask for everything at once.
SpendLimit = Annotated[int, Field(ge=1, le=200)]


class ProviderCredentialResponse(BaseModel):
    """What a settings screen may see about a stored provider key.

    Mirrors `CredentialSummary` exactly. Adding a field here that the dataclass
    does not have would be adding a field the repository never selected -- and
    the only fields it could come from are the ones deliberately excluded.
    """

    id: str
    provider: str

    #: The last four characters of the key, so a user can tell which key is
    #: stored without the key being retrievable. Four is enough to distinguish
    #: two keys a person holds and far too few to reconstruct one.
    last_four: str


class ProviderCredentialRequest(BaseModel):
    """A provider key being stored or replaced.

    The provider is a path parameter rather than a body field, so the URL a
    request was sent to and the credential it writes cannot disagree.
    """

    api_key: PlaintextKey


class BudgetResponse(BaseModel):
    """One configured spend ceiling and how much of it is used.

    `spent_usd` is **readable** and not writable, which is the asymmetry the
    whole budget surface rests on. A member whose request was refused needs to
    see the running total to understand why; nobody needs to edit it.

    Amounts are serialized as strings rather than JSON numbers. A ceiling that
    survives a round trip through a client's floating-point parser is a ceiling
    the client can display, and `0.1 + 0.2` is the reason to not find out
    otherwise (CLAUDE.md §17 -- correctness before convenience).
    """

    id: str

    #: Null for the workspace-wide ceiling, a workflow name for a scoped one.
    workflow_type: str | None

    limit_usd: str
    spent_usd: str
    remaining_usd: str
    period_started_at: str
    period_days: int

    #: Whether the spend circuit breaker has tripped on this budget. Surfaced so
    #: the screen can be honest about *why* calls are being refused rather than
    #: showing a ceiling with room and no explanation.
    breaker_open: bool

    #: Why it tripped. Shown to the workspace because the reason is about that
    #: workspace's own spend -- it names no other tenant and no platform state.
    breaker_reason: str | None


class BudgetUpdateRequest(BaseModel):
    """A change to a workspace's spend ceiling.

    **Accepts `limit_usd` and `period_days`, and refuses anything else.**
    `extra="forbid"` is the load-bearing line: without it, a body carrying
    `spent_usd` would be silently discarded, and "silently discarded" is
    indistinguishable from "accepted" to whoever sent it. A 422 naming the
    rejected field is the honest answer, and it is what makes the refusal
    testable rather than inferred from the absence of an effect.

    The column-level grant added by migration `c9d3b71e08af` is the independent
    second gate: even a route that bypassed this schema could not write
    `spent_usd` over the request connection.
    """

    model_config = ConfigDict(extra="forbid")

    limit_usd: LimitUsd

    #: Optional, so raising a ceiling does not require restating the period.
    #: Omitting it leaves the stored interval untouched rather than resetting it
    #: to a default, which would silently change billing behaviour on an edit
    #: that appears to be about one field.
    period_days: PeriodDays | None = None

    #: Null for the workspace-wide ceiling. Taken from the body rather than the
    #: URL because it identifies *which* of a workspace's budgets is being
    #: configured, not which tenant -- the tenant is always the verified path
    #: parameter, never a body field (`requires(...)` authorizes against that
    #: path parameter, and a body-supplied tenant id would be a caller choosing
    #: their own permission check).
    workflow_type: str | None = None


class SpendRecordResponse(BaseModel):
    """One entry from a workspace's AI spend history.

    Amounts as strings, for the reason `BudgetResponse` states.
    """

    created_at: str
    provider: str
    model: str
    workflow_type: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: str
