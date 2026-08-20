"""Where a workspace's credentials, its spend ceilings, and the router meet.

The router knows how to choose and call a provider; the credential service knows
how to decrypt a key; the spend service knows what a workspace is allowed to
spend. None of them knows about the others, and this is the seam that joins them
without any taking a dependency on another's concerns.

## This is the single choke point, and that is a security property

**Every AI call in ProjectOne passes through `complete()`.** STEP-17 established
that; STEP-18 makes it load-bearing, because it is where the CLAUDE.md §15a
controls are applied. A second path from a route to `AIRouter` would be a path
that spends money without a ceiling -- invisible in this file, and invisible in
the router, which has no idea whether its caller checked a budget.

Two things keep that from happening quietly:

- `AIRouter` is not exposed as its own dependency to any route. The wiring in
  `app/core/dependencies.py` constructs it *for this service*.
- `test_no_ai_call_path_bypasses_governance` asserts the property directly
  rather than trusting the convention.

## The ordering, and why every check precedes the call

    shutdown -> breaker -> budget reservation -> [ PROVIDER CALL ] -> settle

Everything before the call is what makes these limits rather than invoices. The
settlement afterwards is what keeps a reservation from leaking on the failure
path -- see `AISpendService.guard`.

Thin on purpose. Business logic that belongs to *chat* -- conversation history,
memory, prompt assembly -- is [[STEP-23 AI Chat End to End]]'s, and putting any
of it here would make this the class every future AI feature has to modify.
"""

from __future__ import annotations

import uuid

from app.ai.errors import NoProviderAvailableError
from app.ai.governance import ExecutionBudget
from app.ai.pricing import estimate_prompt_tokens, estimated_cost_of
from app.ai.provider import CompletionRequest, CompletionResponse
from app.ai.router import AIRouter
from app.core.logging import get_logger, log_context
from app.services.ai_spend_service import AISpendService
from app.services.provider_credential_service import CredentialReader

logger = get_logger(__name__)

#: The workflow type recorded when a caller does not name one.
#:
#: A concrete default rather than NULL, so every spend record is attributable to
#: *something*. An unattributed row is one no per-workflow ceiling can ever
#: govern, which would make "set a limit on this workflow" silently incomplete.
DEFAULT_WORKFLOW_TYPE = "chat"


class AIService:
    """Runs AI completions for a workspace, within its spend and execution limits."""

    def __init__(
        self,
        router: AIRouter,
        credentials: CredentialReader,
        spend: AISpendService,
    ) -> None:
        """Wire the router to the workspace's credentials and its spend controls.

        `spend` is a required constructor argument, deliberately not optional
        with a permissive default. A default would mean a caller that forgot to
        wire governance still worked -- and worked by spending without a ceiling,
        which is the one failure mode CLAUDE.md §15a treats as equivalent to a
        security vulnerability.
        """
        self._router = router
        self._credentials = credentials
        self._spend = spend

    def complete(
        self,
        workspace_id: uuid.UUID,
        request: CompletionRequest,
        preferred: str | None = None,
        workflow_type: str = DEFAULT_WORKFLOW_TYPE,
        execution_budget: ExecutionBudget | None = None,
        actor_id: uuid.UUID | None = None,
    ) -> CompletionResponse:
        """Run one completion for a workspace, inside every governance control.

        Args:
            workspace_id: The tenant the call is made for. Read from the verified
                request context by the caller, never from a body.
            request: What to generate.
            preferred: The workspace's provider preference, if any.
            workflow_type: What is spending, for per-workflow ceilings and
                attribution.
            execution_budget: The run this call belongs to, when it is part of
                one. A chained or recursive workflow passes the *same* budget to
                every call it makes -- that shared tally is what makes the
                recursion cap real. None means a standalone call, which gets a
                fresh single-call budget rather than an unbounded one.
            actor_id: Who triggered it, for the ledger. None for automated runs.

        Returns:
            The completion, attributed to whichever provider answered.

        Raises:
            AIShutdownError: AI spend is disabled in a scope covering this call.
            SpendBreakerOpenError: the spend circuit breaker has tripped.
            BudgetExceededError: no applicable ceiling had room. Raised before
                any provider is contacted.
            ExecutionLimitExceededError: the run hit its invocation, wall-clock
                or token ceiling.
            NoProviderAvailableError: the workspace has configured no usable
                provider.
            AllProvidersFailedError: every candidate was tried and failed.
        """
        # A fresh budget for a standalone call is not the same as no budget: it
        # still bounds wall-clock time and tokens for this one call, and it means
        # every path through this method has a budget to check rather than a
        # branch that skips the check.
        budget = execution_budget if execution_budget is not None else ExecutionBudget()

        # Checked first, and before anything with a cost. A run that has already
        # exhausted its allowance must not reach the point of reserving money.
        budget.check()

        configured = self._credentials.configured_providers(workspace_id)

        if not configured:
            # An honest, specific failure rather than a generic one: this is the
            # single most likely reason an AI call does not work in a new
            # workspace, and "no provider available" without the reason sends a
            # user looking in the wrong place (CLAUDE.md §15 -- surface
            # uncertainty honestly).
            logger.info(
                log_context(event="ai_no_credentials_configured", workspace_id=workspace_id)
            )
            raise NoProviderAvailableError("This workspace has no AI provider keys configured")

        estimate = estimated_cost_of(
            model=request.model,
            max_tokens=request.max_tokens,
            prompt_tokens=sum(
                estimate_prompt_tokens(message.content) for message in request.messages
            ),
        )

        def resolve_key(provider_name: str) -> str:
            """Decrypt one provider's key, for this workspace only.

            Closes over `workspace_id` from the verified request context, so
            there is no parameter through which a caller could ask for another
            tenant's key -- the same containment the RLS helper functions use
            (RLS Policy Pattern).
            """
            return self._credentials.key_for(workspace_id, provider_name)

        with self._spend.guard(
            workspace_id=workspace_id,
            workflow_type=workflow_type,
            estimated_usd=estimate,
            actor_id=actor_id,
        ) as entry:
            # Inside the guard, so the reservation is settled on every exit path
            # -- including the ones where the router raises after a partial
            # fallback chain. A reservation released only on success would leak
            # on exactly the failures nobody is watching.
            try:
                response = self._router.complete(
                    request=request,
                    available_keys=configured,
                    key_resolver=resolve_key,
                    preferred=preferred,
                )
            except Exception:
                # The invocation counts even though it failed. A failed call that
                # did not count against the run's ceiling would let a workflow
                # retry indefinitely at its own level while the router's ceiling
                # only ever saw single calls -- the runaway CLAUDE.md §15a names.
                budget.record_invocation()
                raise

            entry.record(response.provider, response.model, response.usage)
            budget.record_invocation(response.usage.total_tokens)

        return response
