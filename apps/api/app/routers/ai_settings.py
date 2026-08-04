"""Provider credential, budget and spend endpoints.

**The first HTTP routes that reach the AI layer at all.** STEP-17 built the
router with no routes; STEP-18 built the ceilings, also with none. Everything
here is on the critical path for both tenant isolation and spend, so two rules
govern this module more strictly than any other router:

## 1. No route may produce key material

`ProviderCredentialService.key_for` is the only method in the codebase that
returns a plaintext provider key, and **nothing in this module calls it**. The
read route returns `CredentialSummary` values, a dataclass with no field capable
of carrying a key. A route that returned a stored key -- even to the tenant that
owns it -- would put a credential in a browser, a proxy log, and a user's
clipboard history, and no amount of care at those three places recovers it.

Rotation is therefore *replace*, never *reveal*: a user who has lost their key
stores a new one.

## 2. Roles are enforced in both layers, and the policy is authoritative

Every write here carries a `requires(...)` dependency **and** is refused by an
RLS policy scoped to `owner`/`admin`. That is not redundancy for its own sake:
the policy makes the write impossible, the dependency makes the answer honest.
Without the dependency a `member` would receive a 200 with no effect, or a 404,
where a 403 is the truth. Where the two ever disagree, the policy is correct
([[RLS Policy Pattern]]).

## Errors are raised, never mapped

A governance refusal reaches the client as 402 (a ceiling or execution limit) or
503 with `Retry-After` (a shutdown or tripped breaker) through the handler table
in `app.core.errors`. No route here translates one -- a second translation site
is how two answers to the same condition drift apart.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import (
    AISpendRepositoryDep,
    AuditServiceDep,
    CurrentUserDep,
    ProviderCredentialServiceDep,
    TenantConnectionDep,
    requires,
)
from app.core.permissions import WorkspacePermission, WorkspaceRole
from app.core.user_rate_limit import limit_by_user
from app.repositories.ai_spend import AISpendRepository, Budget
from app.schemas.ai import (
    BudgetResponse,
    BudgetUpdateRequest,
    ProviderCredentialRequest,
    ProviderCredentialResponse,
    ProviderName,
    SpendLimit,
    SpendRecordResponse,
)
from app.services.audit_service import AuditAction

router = APIRouter(prefix="/workspaces/{workspace_id}/ai", tags=["ai-settings"])


def _budget_response(budget: Budget) -> BudgetResponse:
    """Render a stored ceiling for a settings screen.

    `period_days` is derived from the stored interval rather than stored
    separately, so the value a screen shows and the value enforcement uses cannot
    disagree. Truncated to whole days deliberately: the write side only accepts
    whole days, so a fractional interval can only come from the platform's own
    provisioning path, and rounding it up would report a longer period than the
    one actually in force.
    """
    return BudgetResponse(
        id=str(budget.id),
        workflow_type=budget.workflow_type,
        limit_usd=str(budget.limit_usd),
        spent_usd=str(budget.spent_usd),
        remaining_usd=str(budget.remaining_usd),
        period_started_at=budget.period_started_at.isoformat(),
        period_days=max(1, int(budget.period_interval.total_seconds() // 86400)),
        breaker_open=budget.is_breaker_open,
        breaker_reason=budget.breaker_reason,
    )


# ----------------------------------------------------------------------------
# Provider credentials (BYOK)
# ----------------------------------------------------------------------------


@router.get(
    "/providers",
    response_model=list[ProviderCredentialResponse],
    summary="Provider keys configured for a workspace",
)
def list_provider_credentials(
    workspace_id: uuid.UUID,
    credentials: ProviderCredentialServiceDep,
    _role: Annotated[WorkspaceRole, Depends(requires(WorkspacePermission.VIEW_WORKSPACE))],
) -> list[ProviderCredentialResponse]:
    """Return which providers this workspace holds keys for, and nothing more.

    Readable by every live member rather than admins only, matching the audit
    trail's reasoning: *whether* a workspace can make AI calls is something the
    people making them need to know, and the response carries no secret. The
    write routes below are where the role asymmetry lives.

    The workspace id is a filter here, not the security control -- RLS is. A bug
    in the filter narrows the result; it cannot widen it past the policy.
    """
    summaries = credentials.list_summaries(workspace_id)

    return [
        ProviderCredentialResponse(
            id=str(summary.id),
            provider=summary.provider,
            last_four=summary.last_four,
        )
        for summary in summaries
    ]


@router.put(
    "/providers/{provider}",
    response_model=ProviderCredentialResponse,
    summary="Store or replace a workspace's provider key",
    # Tight, and for a different reason than most limits here. This route is the
    # one place a caller submits a secret, so a high ceiling would make it a
    # convenient oracle for testing stolen keys against a workspace's own
    # provider account. A person configuring a key does it once.
    dependencies=[Depends(limit_by_user("ai-provider-key", limit=10, window_seconds=60))],
)
def store_provider_credential(
    workspace_id: uuid.UUID,
    provider: ProviderName,
    request: ProviderCredentialRequest,
    user: CurrentUserDep,
    credentials: ProviderCredentialServiceDep,
    audit: AuditServiceDep,
    _role: Annotated[WorkspaceRole, Depends(requires(WorkspacePermission.UPDATE_WORKSPACE))],
) -> ProviderCredentialResponse:
    """Encrypt and store a provider key, replacing any existing one.

    `PUT` rather than `POST`: storing a key for a provider that already has one
    replaces it, so the operation is idempotent on the pair
    (workspace, provider) -- sending the same key twice leaves the same state.
    That is what `PUT` means, and it is also what makes a retried request after a
    timeout safe.

    The response carries `last_four` and no key. **The key is never returned by
    any route in this codebase**, including this one, immediately after it was
    submitted -- echoing it back would put it in the response body of a request
    that a proxy may log, for the benefit of a client that already has it.

    Raises:
        HTTPException: 422 when the key is too short to be plausible. Raised
            before anything is written, so a mistyped key does not replace a
            working credential.
    """
    try:
        summary = credentials.store(
            workspace_id=workspace_id,
            provider=provider,
            plaintext_key=request.api_key,
            created_by=user.id,
        )
    except ValueError as error:
        # The service's own rejection, surfaced rather than re-derived. Its
        # message names the problem without quoting the value -- an error
        # containing the rejected key would defeat the point of the route.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from None

    # After the write, never before: the audit trail records what happened, and
    # a record written first would claim a key was stored even if the insert
    # then failed. `last_four` is deliberately **not** recorded -- an audit row
    # is readable by every member, and four characters of a credential in a
    # widely-readable table is a leak that took an extra step.
    audit.record(
        AuditAction.PROVIDER_KEY_STORED,
        workspace_id=workspace_id,
        actor=user,
        provider=provider,
    )

    return ProviderCredentialResponse(
        id=str(summary.id),
        provider=summary.provider,
        last_four=summary.last_four,
    )


@router.delete(
    "/providers/{provider}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke a workspace's provider key",
)
def revoke_provider_credential(
    workspace_id: uuid.UUID,
    provider: ProviderName,
    user: CurrentUserDep,
    credentials: ProviderCredentialServiceDep,
    audit: AuditServiceDep,
    _role: Annotated[WorkspaceRole, Depends(requires(WorkspacePermission.UPDATE_WORKSPACE))],
) -> None:
    """Soft-delete the stored key for one provider.

    A `DELETE` verb over a soft delete, the honest mapping this codebase uses
    throughout: from the caller's side the credential becomes unusable and
    unreachable, which is what revoking means to them. The row survives as
    history, and the key it holds stays encrypted under a key no route can reach.

    Raises:
        HTTPException: 404 when there was no live credential to revoke. Reporting
            204 for a no-op would tell a user their key was removed when nothing
            happened -- and for a security action, a false confirmation is worse
            than an error. Note RLS makes "not yours" and "not there" identical
            here, which is correct: distinguishing them would confirm the
            existence of another tenant's credential.
    """
    if not credentials.revoke(workspace_id, provider):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No key is stored for this provider",
        )

    audit.record(
        AuditAction.PROVIDER_KEY_REVOKED,
        workspace_id=workspace_id,
        actor=user,
        provider=provider,
    )


# ----------------------------------------------------------------------------
# Budgets and spend
# ----------------------------------------------------------------------------


@router.get(
    "/budgets",
    response_model=list[BudgetResponse],
    summary="Spend ceilings configured for a workspace",
)
def list_budgets(
    workspace_id: uuid.UUID,
    connection: TenantConnectionDep,
    _role: Annotated[WorkspaceRole, Depends(requires(WorkspacePermission.VIEW_WORKSPACE))],
) -> list[BudgetResponse]:
    """Return every ceiling this workspace has configured, and its usage.

    **Every member reads, only owners and admins write** -- the asymmetry
    migration `b2e6f0a71c94` encodes, and both halves matter. A tripped ceiling
    has to be explainable to the person whose request was refused, and a refusal
    they cannot investigate is the silent failure CLAUDE.md §15a's graceful
    degradation rule exists to prevent.

    Read over the **tenant** connection rather than the privileged one that
    enforcement uses. The difference is deliberate: enforcement must find a
    ceiling whether or not the caller can see it, while a *display* must show
    only what the caller is entitled to. Reading this privileged would be a
    cross-tenant read waiting for a filter bug.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, workspace_id, workflow_type, limit_usd, spent_usd,
                   period_started_at, period_interval,
                   breaker_tripped_at, breaker_reason
            FROM public.ai_budgets
            WHERE workspace_id = %s AND deleted_at IS NULL
            ORDER BY workflow_type NULLS FIRST
            """,
            (workspace_id,),
        )
        rows = cursor.fetchall()

    return [
        _budget_response(
            Budget(
                id=row[0],
                workspace_id=row[1],
                workflow_type=row[2],
                limit_usd=row[3],
                spent_usd=row[4],
                period_started_at=row[5],
                period_interval=row[6],
                breaker_tripped_at=row[7],
                breaker_reason=row[8],
            )
        )
        for row in rows
    ]


@router.put(
    "/budgets",
    response_model=BudgetResponse,
    summary="Create or update a spend ceiling",
    # Changing a ceiling is a deliberate act performed occasionally. The limit is
    # low enough that a script rewriting a budget in a loop meets it and a person
    # never does.
    dependencies=[Depends(limit_by_user("ai-budget", limit=10, window_seconds=60))],
)
def upsert_budget(
    workspace_id: uuid.UUID,
    request: BudgetUpdateRequest,
    user: CurrentUserDep,
    spend: AISpendRepositoryDep,
    audit: AuditServiceDep,
    _role: Annotated[WorkspaceRole, Depends(requires(WorkspacePermission.UPDATE_WORKSPACE))],
) -> BudgetResponse:
    """Set a workspace's spend ceiling for one scope.

    **`spent_usd` cannot be changed here, by three independent mechanisms.**
    `BudgetUpdateRequest` forbids extra fields, so sending it is a 422 rather
    than a silent no-op; this handler never passes it on; and migration
    `c9d3b71e08af` revoked the table-wide UPDATE grant in favour of one on
    `limit_usd` and `period_interval` only, so the request connection could not
    write it even if the two layers above were bypassed.

    The last of those is the one that holds when a future route forgets, which is
    why it exists despite the first two being sufficient today.

    Written through `AISpendRepository`, which uses the **privileged** connection.
    That is a deliberate departure from the RLS-first default and it deserves
    stating: the repository's other budget methods maintain `spent_usd` during
    reserve/settle and must run privileged, and giving one method a second
    connection type would make "which connection does this run on" a per-method
    question rather than a per-repository one. Authorization is not weakened by
    it -- `requires(UPDATE_WORKSPACE)` has already refused a `member` with a 403
    before this body runs, and the workspace id comes from the verified path
    parameter that the same dependency authorized against.
    """
    period = None if request.period_days is None else dt.timedelta(days=request.period_days)

    spend.upsert_budget(
        workspace_id=workspace_id,
        workflow_type=request.workflow_type,
        limit_usd=request.limit_usd,
        period_interval=period,
    )

    audit.record(
        AuditAction.BUDGET_UPDATED,
        workspace_id=workspace_id,
        actor=user,
        workflow_type=request.workflow_type,
        limit_usd=str(request.limit_usd),
    )

    # Read back rather than constructing a response from the request. What the
    # caller needs to see is the stored state -- including `spent_usd`, the
    # period start, and a breaker that is still open -- none of which the request
    # carried. Echoing the input would render a screen showing what was asked for
    # rather than what is in force.
    stored = spend.budgets_for(workspace_id, request.workflow_type or "")

    for budget in stored:
        if budget.workflow_type == request.workflow_type:
            return _budget_response(budget)

    # Unreachable in practice -- the upsert above either updated or inserted the
    # row this loop looks for. Defensive rather than dead: returning a
    # fabricated response would be worse than a loud failure.
    raise HTTPException(  # pragma: no cover - defensive
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="The budget could not be read back after being saved",
    )


@router.get(
    "/spend",
    response_model=list[SpendRecordResponse],
    summary="A workspace's AI spend history",
)
def read_spend_history(
    workspace_id: uuid.UUID,
    connection: TenantConnectionDep,
    _role: Annotated[WorkspaceRole, Depends(requires(WorkspacePermission.VIEW_WORKSPACE))],
    limit: Annotated[SpendLimit, Query()] = 50,
) -> list[SpendRecordResponse]:
    """Return recent AI spend for a workspace, newest first.

    Runs over the tenant connection, and `read_records_for_workspace` takes that
    connection rather than opening one -- so this route structurally cannot read
    privileged, the same defence `AuditRepository.read_for_workspace` uses.

    Readable by every member. The ledger says what this workspace spent on its
    own provider account; the people spending it are entitled to see it, and a
    cost control nobody can inspect is one nobody can act on.
    """
    records = AISpendRepository.read_records_for_workspace(connection, workspace_id, limit)

    return [
        SpendRecordResponse(
            created_at=str(record["created_at"]),
            provider=str(record["provider"]),
            model=str(record["model"]),
            workflow_type=str(record["workflow_type"]),
            prompt_tokens=int(str(record["prompt_tokens"])),
            completion_tokens=int(str(record["completion_tokens"])),
            cost_usd=str(record["cost_usd"]),
        )
        for record in records
    ]
