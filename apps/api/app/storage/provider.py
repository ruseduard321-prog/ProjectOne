"""The contract every storage provider implements, and the vocabulary around it.

This module is deliberately the *only* thing a caller knows about object storage.
It imports no HTTP client, no vendor SDK and no FastAPI: a provider is a class
with four methods, and callers depend on this abstraction rather than on any
implementation of it (CLAUDE.md §7 -- provider independence, §12 -- dependency
inversion). Cloudflare R2 is the first adapter behind it, and that is an
implementation detail rather than an architectural commitment
([[ADR-004 Object Storage Provider and Tenant-Safe Key Construction]]).

## Why an abstract base class rather than a Protocol

The same reasoning `app/ai/provider.py` records, and it applies here with more
force. A `Protocol` is structurally satisfied by any object with the right method
shape, so an adapter that forgot a method or returned the wrong type would be
accepted silently and fail when a real user first uploaded a file. An ABC fails
at import, which is the only time this class of mistake is cheap.

## Why no method takes a key

Every operation takes a `workspace_id` and a `logical_name`, and the key is
constructed inside by `app.storage.keys`. **No caller can supply a raw object
key**, because no signature accepts one
([[ADR-004 Object Storage Provider and Tenant-Safe Key Construction]] §4).

This is the isolation mechanism, not a convenience. Object storage has no Row
Level Security, so unlike every other tenant boundary in this product there is
no database backstop if a caller gets it wrong. An interface accepting a raw key
could not be made safe by documentation -- the first caller to interpolate user
input into one would reintroduce exactly the traversal bug the key module exists
to prevent, and it would look entirely ordinary at the call site.

## What is deliberately not on this interface

Kept narrow on purpose, following the restraint `app/ai/provider.py` established
(CLAUDE.md §29/§35 -- build for what is scheduled, not for what might arrive):

- **No listing.** No scheduled step enumerates a workspace's objects, and a list
  operation is the one most likely to be written with a caller-supplied prefix --
  which is precisely the raw-path surface this design removes.
- **No multipart or resumable upload.** [[STEP-28 Asset Upload and Download]]
  owns the upload transport. Guessing its shape now means two implementations of
  a contract no caller exercises.
- **No copy or move.** Nothing schedules them.
- **No quota accounting or lifecycle rules** -- [[STEP-33 Storage Quotas and
  Lifecycle]].
- **No media processing of any kind.**

Adding a method later is one method here and one implementation per adapter.
Removing a speculative one is a breaking change to every adapter that implemented
it.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True)
class StoredObject:
    """What a `put` produced, described without reference to any vendor.

    Frozen because this is a record of something that already happened; a
    mutable result is one a later caller can edit into a description of an
    object that does not exist.

    `key` is the *constructed* key, returned so the caller can persist it (this
    is what `assets.storage_path` stores). It is an output of construction, never
    an input to it -- returning a key does not let a caller invent one, because
    no method accepts one.
    """

    key: str
    size_bytes: int
    content_type: str


class StorageProvider(ABC):
    """One object-storage backend, behind a contract callers can depend on.

    Implementations live in `app/storage/providers/`. Each is responsible for its
    own wire format, its own authentication and its own error translation -- and
    for nothing else.

    **Every implementation constructs keys with `app.storage.keys` and refuses
    any operation on an object outside the named workspace.** That obligation is
    on the adapter rather than on callers because callers are the thing this
    design does not trust with paths.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the stable identifier for this provider.

        Logged against storage operations and used as a dictionary key. A wire
        value in all but name, so it must not be derived from a class name
        somebody might reasonably rename.
        """

    @abstractmethod
    def put(
        self,
        workspace_id: uuid.UUID,
        logical_name: str,
        data: bytes,
        content_type: str,
    ) -> StoredObject:
        """Store bytes as one workspace's object.

        Args:
            workspace_id: The owning workspace. The key is built from it.
            logical_name: The caller's name for the object, validated as a
                single safe path segment.
            data: The bytes to store.
            content_type: The MIME type to record with the object.

        Returns:
            The stored object, including the key that was constructed.

        Raises:
            InvalidLogicalNameError: if `logical_name` is unsafe.
            StorageUnavailableError: if the backend could not be reached.
            StorageAccessDeniedError: if the credential was refused.
        """

    @abstractmethod
    def get(self, workspace_id: uuid.UUID, logical_name: str) -> bytes:
        """Return one workspace's object as bytes.

        Args:
            workspace_id: The owning workspace.
            logical_name: The object's logical name.

        Returns:
            The object's bytes.

        Raises:
            InvalidLogicalNameError: if `logical_name` is unsafe.
            ObjectNotFoundError: if no such object exists.
            StorageAccessDeniedError: if the credential was refused.
            StorageUnavailableError: if the backend could not be reached.
        """

    @abstractmethod
    def signed_url(
        self,
        workspace_id: uuid.UUID,
        logical_name: str,
        expires_in: timedelta,
    ) -> str:
        """Return a time-limited URL granting direct read access to one object.

        The mechanism by which bytes reach a browser without the object being
        public and without proxying them through the API.

        `expires_in` is required rather than defaulted. A default would be a
        security parameter chosen once by whoever wrote the adapter and then
        inherited silently by every caller; making it explicit forces the
        decision at the call site, where the sensitivity of the object is known.

        Args:
            workspace_id: The owning workspace.
            logical_name: The object's logical name.
            expires_in: How long the URL stays valid. Implementations reject a
                non-positive duration, and each backend has its own upper bound.

        Returns:
            A URL that grants read access until it expires.

        Raises:
            InvalidLogicalNameError: if `logical_name` is unsafe.
            ValueError: if `expires_in` is outside the backend's permitted range.
            StorageUnavailableError: if the URL could not be generated.
        """

    @abstractmethod
    def delete(self, workspace_id: uuid.UUID, logical_name: str) -> None:
        """Delete one workspace's object.

        Idempotent: deleting an object that does not exist is not an error, so a
        retried deletion does not fail on its second attempt.

        What is **not** tolerated is deleting outside the workspace's namespace.
        That fails closed, before any request reaches the backend.

        Args:
            workspace_id: The owning workspace.
            logical_name: The object's logical name.

        Raises:
            InvalidLogicalNameError: if `logical_name` is unsafe.
            StorageAccessDeniedError: if the object is not this workspace's.
            StorageUnavailableError: if the backend could not be reached.
        """
