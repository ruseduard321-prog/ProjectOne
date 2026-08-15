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
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from app.core.config import Settings
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

    @staticmethod
    def retention_cutoff(settings: Settings) -> datetime | None:
        """Return the timestamp before which audit rows have expired.

        **FA-07.** The window is the owner's decision of 2026-08-15: 90 days,
        configurable before public release.

        Returns None when retention is disabled, and that is the whole reason
        this returns an optional rather than a datetime. `audit_retention_days
        = 0` means *retain indefinitely*, and the dangerous misreading is "keep
        nothing" — a cutoff of `now` would expire the entire log. Refusing to
        produce a cutoff at all makes that outcome unreachable rather than
        merely unlikely.

        Args:
            settings: The configuration holding the window.

        Returns:
            The cutoff, or None when nothing should ever be purged.
        """
        if settings.audit_retention_days <= 0:
            return None

        return datetime.now(UTC) - timedelta(days=settings.audit_retention_days)

    @staticmethod
    def retention_disclosure(settings: Settings) -> str:
        """Describe the retention window in the words a user is owed.

        CLAUDE.md §16 requires the audit-log exception to user erasure to be
        *disclosed* as bounded, not merely to be bounded. Deriving the sentence
        from the configured value is what stops the disclosure and the behaviour
        drifting apart — the failure mode of every hardcoded privacy notice.
        """
        if settings.audit_retention_days <= 0:
            return "Audit events are retained indefinitely."

        return (
            f"Audit events are retained for {settings.audit_retention_days} days, "
            "then permanently deleted."
        )

    def purge_expired(self, settings: Settings) -> int:
        """Delete audit events past the retention window.

        Unlike `record`, this does **not** swallow failures. A silent audit
        write failure loses one line; a silent purge failure means retention is
        not happening, which is a compliance position quietly becoming false —
        the caller needs to know so it can alert (CLAUDE.md §26).

        Args:
            settings: The configuration holding the retention window.

        Returns:
            How many rows were deleted. Zero when retention is disabled, and the
            repository is not asked to delete at all in that case.
        """
        cutoff = self.retention_cutoff(settings)

        if cutoff is None:
            return 0

        deleted = self._audit.purge_older_than(cutoff)

        logger.info(
            log_context(
                event="audit_retention_purge",
                retention_days=settings.audit_retention_days,
                deleted=deleted,
            )
        )

        return deleted

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
