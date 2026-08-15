"""Storage failures, typed by what a caller can do about them.

Adapters translate their vendor's exceptions into this hierarchy, so nothing
above the adapter boundary needs to know what a `botocore.exceptions.ClientError`
is ([[ADR-004 Object Storage Provider and Tenant-Safe Key Construction]] §3).

    StorageError                  (base -- never raised directly)
    +-- ObjectNotFoundError       the object does not exist
    +-- StorageAccessDeniedError  refused: not this workspace's object, or the
    |                             credential cannot perform the operation
    +-- StorageUnavailableError   the backend failed or could not be reached

The split is by **caller response**, not by HTTP status: a missing object is a
4xx a caller can handle, a refusal is a security-relevant event, and an outage is
a retry-or-degrade decision. Organising by vendor error code would push that
interpretation into every call site.
"""

from __future__ import annotations


class StorageError(Exception):
    """Base class for every storage failure.

    Never raised directly. Carries a `public_message` like the rest of this
    codebase: detail stays in the log, and what reaches a user says what
    happened without exposing bucket names, keys or credentials
    (CLAUDE.md §24).
    """

    #: Safe to surface to an API caller. Overridden by subclasses.
    public_message = "The storage backend could not complete the request."

    def __init__(self, message: str | None = None) -> None:
        """Initialise the error, defaulting to the class's public message."""
        super().__init__(message or self.public_message)


class ObjectNotFoundError(StorageError):
    """No object exists at the requested key."""

    public_message = "The requested file does not exist."


class StorageAccessDeniedError(StorageError):
    """The operation was refused.

    Raised both for a credential the backend rejected and — more importantly —
    for an operation naming an object outside the calling workspace's namespace.
    The second case is refused by ProjectOne before any request is issued, which
    is what "fails closed" means here: the backend is never asked.
    """

    public_message = "You do not have access to that file."


class StorageUnavailableError(StorageError):
    """The storage backend failed or could not be reached."""

    public_message = "The storage backend is temporarily unavailable."
