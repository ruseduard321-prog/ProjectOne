"""Uploading an asset's bytes, and handing them back through a signed URL.

The service [[STEP-28 Asset Upload and Download]] adds. It composes two things
that already exist and deliberately owns neither: `ProjectService` holds the
lifecycle and the asset rows, `StorageProvider` holds the bytes. What lives here
is the *sequencing* between them, which is the part that can go wrong.

## The ordering, and what each side guarantees

**A database transaction cannot span the storage call.** PostgreSQL can roll back
its own write; it has no idea an object was put in a bucket, and no way to undo
it. So the two systems are made consistent by ordering rather than by atomicity:

    1. create the asset row with a null `storage_path`
    2. put the bytes
    3. point the row at what was stored

Each step's failure leaves a state that is *recoverable and honest*:

- **Failing at 1** leaves nothing. No row, no object.
- **Failing at 2** leaves a row whose `storage_path` is null. It is visible in
  the project, it holds no bytes, and the API says so rather than offering a
  download of nothing. The user can delete it or upload again.
- **Failing at 3** would leave an object no row references — the one genuinely
  invisible outcome, because there is no listing operation to find it with
  (ADR-004). So it is the one case that is actively cleaned up: the object is
  deleted before the error propagates.

The reverse ordering — put first, then create the row — is what makes the bad
case the *unrecoverable* one, and is why it is not used. An object stored before
a row exists is unreferenced from the moment it lands, and if the row insert then
fails there is nothing left pointing at it.

## Why the asset table is the only index

`StorageProvider` has no listing operation, on purpose. Nothing can enumerate a
workspace's objects, so **the asset rows are the sole record of what exists in
storage**. That is what makes the null-`storage_path` outcome acceptable and the
orphaned-object outcome not, and it is why erasure
(`app.services.data_ownership_service`) is row-driven too.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta

from app.core.logging import get_logger, log_context
from app.repositories.projects import Asset
from app.schemas.project import AssetKind
from app.services.asset_content import SNIFF_BYTES, validate_upload
from app.services.project_service import ProjectService
from app.storage.logical_names import derive_logical_name, extension_of
from app.storage.provider import StorageProvider

logger = get_logger(__name__)

#: How long a download URL stays valid.
#:
#: **15 minutes, set by the project owner on 2026-08-16** ([[STEP-28 Asset Upload
#: and Download#Decisions]] D3).
#:
#: A signed URL is a **bearer capability**: whoever holds the string can read the
#: object, with no authentication and no way to tell who used it. The backend
#: bounds expiry at 7 days and supplies no default deliberately, so the choice
#: belongs here, at the call site that knows what is being handed out.
#:
#: 15 minutes is long enough for a browser to fetch an asset it is about to
#: display — including a slow connection and a retry — and short enough that a
#: URL leaked through a referrer header, a shared screenshot or a log stops
#: working before it is useful to anyone.
DOWNLOAD_URL_TTL = timedelta(minutes=15)


class AssetFileNotFoundError(Exception):
    """The asset exists, but no bytes are attached to it.

    Distinct from "no such asset" internally and **identical to it from the
    outside**: both answer 404. Keeping them separate here lets the service log
    the difference — an asset with a null `storage_path` is the visible residue
    of a failed upload, and that is worth being able to count — without offering
    a client an oracle for which assets exist but are empty.
    """

    public_message = "No file is attached to that asset."


@dataclass(frozen=True)
class SignedDownload:
    """A time-limited URL for one asset's bytes."""

    url: str

    #: Restated in seconds so a client can schedule a refresh without parsing
    #: the URL's own expiry parameters, which are provider-specific.
    expires_in_seconds: int


class AssetStorageService:
    """Moves asset bytes in and out of the configured storage backend."""

    def __init__(self, projects: ProjectService, storage: StorageProvider) -> None:
        """Store the collaborators; this service holds no state of its own."""
        self._projects = projects
        self._storage = storage

    def upload(
        self,
        *,
        workspace_id: uuid.UUID,
        project_id: uuid.UUID,
        name: str,
        kind: AssetKind,
        data: bytes,
        declared_content_type: str | None,
        filename: str | None,
        created_by: uuid.UUID,
    ) -> Asset:
        """Validate an upload, store its bytes, and record it against a project.

        Keyword-only because the call site otherwise reads as eight
        indistinguishable positional values, two of which are user-controlled
        strings that must not be transposed.

        Args:
            workspace_id: The owning workspace — the tenant boundary.
            project_id: The project the asset attaches to.
            name: The human-readable asset name. Stored as given.
            kind: What the client claims this asset is.
            data: The uploaded bytes, already bounded by the caller.
            declared_content_type: The MIME type the client declared.
            filename: The client's filename. Used for its extension only.
            created_by: The verified caller.

        Returns:
            The asset row, with `storage_path` populated.

        Raises:
            AssetContentError: the bytes were refused. See `asset_content`.
            ProjectNotFoundError: no live project matched.
            StorageError: the backend refused or could not be reached.
            ValueError: the asset name is blank.
        """
        extension = extension_of(filename)

        # Validated *before* the row is created, so a refused upload leaves
        # nothing behind at all. Every check here is on the bytes and the
        # client's claims about them -- path safety is not among them, because
        # no path exists yet and the one that will is not caller-supplied.
        accepted = validate_upload(
            kind=kind,
            declared_content_type=declared_content_type,
            extension=extension,
            head=data[:SNIFF_BYTES],
            size_bytes=len(data),
        )

        # Step 1. The row, with no storage path: it points at nothing yet
        # because nothing has been stored yet.
        asset = self._projects.add_asset(
            workspace_id=workspace_id,
            project_id=project_id,
            name=name,
            kind=kind,
            created_by=created_by,
        )

        # Derived from the row's own id, which is why two uploads of the same
        # filename cannot overwrite each other -- see `derive_logical_name`.
        logical_name = derive_logical_name(asset.id, filename)

        # Step 2. The bytes. A failure here propagates and leaves the row with a
        # null `storage_path`: visible, empty, and safe to retry or delete. It is
        # deliberately *not* cleaned up -- a row is cheap and discoverable, and
        # deleting it would discard the only evidence that an upload was
        # attempted.
        stored = self._storage.put(
            workspace_id=workspace_id,
            logical_name=logical_name,
            data=data,
            content_type=accepted.mime,
        )

        # Step 3. Point the row at the object. The one failure that would leave
        # an object nothing references, so it is the one that cleans up.
        try:
            updated = self._projects.attach_storage_path(
                workspace_id=workspace_id,
                asset_id=asset.id,
                storage_path=stored.locator,
            )
        except Exception:
            self._discard_orphan(workspace_id, stored.locator, asset.id)
            raise

        logger.info(
            log_context(
                event="asset_uploaded",
                workspace_id=workspace_id,
                project_id=project_id,
                asset_id=asset.id,
                size_bytes=stored.size_bytes,
                content_type=stored.content_type,
            )
        )

        return updated

    def download_url(self, workspace_id: uuid.UUID, asset_id: uuid.UUID) -> SignedDownload:
        """Return a time-limited URL for one asset's bytes.

        **The row is resolved before the storage call, and that ordering is the
        tenant boundary.** RLS refuses another workspace's row, so a caller who
        should not see this asset gets a 404 here and no URL is ever signed. A
        route that signed first and checked afterwards would have handed out a
        working capability before deciding whether it was allowed to.

        `storage_path` and `workspace_id` are passed to the provider exactly as
        the row holds them. **Nothing is parsed, split, stripped or prefixed** —
        the locator *is* the logical name, and the full object key is internal to
        the storage layer (ADR-004).

        Args:
            workspace_id: The owning workspace.
            asset_id: The asset to sign a URL for.

        Returns:
            The URL and how long it remains valid.

        Raises:
            ProjectNotFoundError: no live asset matched, or RLS hid it.
            AssetFileNotFoundError: the asset exists but holds no bytes.
            StorageError: the URL could not be generated.
        """
        asset = self._projects.get_asset(workspace_id, asset_id)

        if asset.storage_path is None:
            # An asset row with no object. Ordinary rather than exceptional: it
            # is what a failed upload leaves behind, and what every asset created
            # through the metadata-only route has always looked like.
            logger.info(
                log_context(
                    event="asset_download_without_object",
                    workspace_id=workspace_id,
                    asset_id=asset_id,
                )
            )
            raise AssetFileNotFoundError()

        url = self._storage.signed_url(
            workspace_id=asset.workspace_id,
            logical_name=asset.storage_path,
            expires_in=DOWNLOAD_URL_TTL,
        )

        logger.info(
            log_context(
                event="asset_download_signed",
                workspace_id=workspace_id,
                asset_id=asset_id,
                expires_in_seconds=int(DOWNLOAD_URL_TTL.total_seconds()),
            )
        )

        return SignedDownload(
            url=url,
            expires_in_seconds=int(DOWNLOAD_URL_TTL.total_seconds()),
        )

    def _discard_orphan(
        self,
        workspace_id: uuid.UUID,
        locator: str,
        asset_id: uuid.UUID,
    ) -> None:
        """Delete an object whose row could not be updated to reference it.

        Best-effort, and it must stay that way: this runs while another exception
        is propagating, and letting a cleanup failure replace the original error
        would report the symptom instead of the cause.

        A failure here is logged at **error** rather than swallowed, because the
        result is an object no row references and no listing operation can find —
        the one storage state this design cannot detect later (CLAUDE.md §26).
        `delete` is idempotent, so the log line is enough for a human to finish
        the job by hand.
        """
        try:
            self._storage.delete(workspace_id=workspace_id, logical_name=locator)
        except Exception:  # noqa: BLE001 - see docstring; never mask the original
            logger.error(
                log_context(
                    event="asset_orphan_object_left",
                    workspace_id=workspace_id,
                    asset_id=asset_id,
                )
            )
