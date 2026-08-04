"""Recording who did what, to which workspace, and when.

The distinction this exists to preserve: **request logging says a request
happened; an audit log says who changed what.** STEP-12 built the former, and
[[API Architecture]] has required the latter since before there was anything to
audit. STEP-13 creates the first consequential mutations -- a tenant boundary
being created, a member added or removed, ownership changing hands -- so this is
where the gap closes.

## Failures are swallowed, deliberately

`record` never raises. An audit write failing must not turn a *successful*
member removal into a 500 the caller retries, because the retry performs the
action a second time -- an audit-infrastructure problem would become a data
problem, which is strictly worse than a missing audit line.

The failure is logged at `exception` level so it is loud and alertable rather
than silent. This is a considered trade-off, not an oversight: for the actions
recorded here, availability of the operation outweighs completeness of the
trail. **An action whose audit record is legally required to be atomic with it
must not use this method** -- it needs a write inside the operation's own
transaction, and that is a different mechanism, to be built when such an action
exists.
"""

import uuid
from enum import StrEnum
from typing import Any

from app.core.logging import get_logger, log_context
from app.repositories.audit import AuditEntry, AuditRepository
from app.services.token_service import AuthenticatedUser

logger = get_logger(__name__)


class AuditAction(StrEnum):
    """The vocabulary of auditable actions.

    Values match `ck_audit_log_action_valid` exactly. `StrEnum` so a value
    compares equal to the string the database stores, keeping the boundary
    between the two layers free of conversions that could silently disagree --
    the same reasoning as `WorkspaceRole`.

    Adding a value here means altering that CHECK constraint in a migration.
    The constraint is what makes an unrecognised action a loud failure rather
    than a row nobody can interpret later.
    """

    WORKSPACE_CREATED = "workspace.created"
    MEMBER_ADDED = "member.added"
    MEMBER_REMOVED = "member.removed"
    MEMBER_LEFT = "member.left"
    OWNERSHIP_TRANSFERRED = "ownership.transferred"

    # Added by STEP-19, alongside migration `c9d3b71e08af` which widens the
    # CHECK constraint to accept them. A provider key authorizes spend against
    # the workspace's own provider account, so its appearance and disappearance
    # are security questions somebody will eventually need answered -- and a
    # budget ceiling is a decision about money, where "who changed it" is the
    # first question asked after a surprising invoice.
    PROVIDER_KEY_STORED = "provider_key.stored"
    PROVIDER_KEY_REVOKED = "provider_key.revoked"
    BUDGET_UPDATED = "budget.updated"


class AuditService:
    """Records consequential actions to the audit log."""

    def __init__(self, audit: AuditRepository) -> None:
        """Store the repository writes go through."""
        self._audit = audit

    def record(
        self,
        action: AuditAction,
        workspace_id: uuid.UUID,
        actor: AuthenticatedUser,
        target_id: uuid.UUID | None = None,
        **detail: Any,  # noqa: ANN401 - action-specific detail, by design
    ) -> None:
        """Record one action, never raising.

        Call this **after** the operation it describes has committed. The audit
        write does not share the operation's transaction (see
        `AuditRepository.record`), so recording first would leave a trail
        claiming something happened that then rolled back.

        Args:
            action: What happened.
            workspace_id: The workspace it happened in.
            actor: The verified caller. Taken as the whole identity rather than
                an id so the email snapshot cannot be supplied by a caller --
                it comes from the token, like every other identity fact.
            target_id: Who or what was acted on, where that differs from the
                workspace itself.
            **detail: Action-specific context worth keeping.
        """
        try:
            self._audit.record(
                AuditEntry(
                    action=action.value,
                    workspace_id=workspace_id,
                    actor_id=actor.id,
                    actor_email=actor.email,
                    target_id=target_id,
                    detail=dict(detail),
                )
            )
        except Exception:
            # Loud, but not fatal -- see the module docstring. `log_context`
            # redacts credential-shaped values, though nothing here should carry
            # one: `detail` holds roles and names, never tokens.
            logger.exception(
                log_context(
                    event="audit_write_failed",
                    action=action.value,
                    workspace_id=workspace_id,
                )
            )
