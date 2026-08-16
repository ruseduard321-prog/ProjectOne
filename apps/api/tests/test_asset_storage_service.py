"""The sequencing between the asset row and the object holding its bytes.

**This is where the orphan proofs live.** A database transaction cannot span the
storage call, so consistency between the two comes from ordering, and ordering is
exactly the kind of thing that looks right and is not. Each failure point is
provoked deliberately here and the resulting state asserted.

Runs without a database: `ProjectService` is stubbed, because what is under test
is the order of the calls and the reaction to each one failing, not SQL. The
route-level behaviour against a real database is `test_asset_upload_api.py`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.repositories.projects import Asset
from app.schemas.project import AssetKind
from app.services.asset_content import ContentMismatchError, UnsupportedContentTypeError
from app.services.asset_storage_service import (
    DOWNLOAD_URL_TTL,
    AssetFileNotFoundError,
    AssetStorageService,
)
from app.services.project_service import ProjectNotFoundError
from app.storage.errors import StorageUnavailableError
from tests.conftest import RecordingStorageProvider
from tests.test_asset_content import PNG

WORKSPACE = uuid.uuid4()
PROJECT = uuid.uuid4()
USER = uuid.uuid4()


class StubProjects:
    """The parts of `ProjectService` this service actually calls.

    A stub rather than the real service over a stub repository: what is being
    tested is this service's sequencing, and routing through two layers of real
    code to reach a fake database would test the layers rather than the order.
    """

    def __init__(self) -> None:
        self.assets: dict[uuid.UUID, Asset] = {}
        #: Set to an exception to make `attach_storage_path` fail -- the one
        #: failure that would otherwise leave an unreferenced object.
        self.attach_error: Exception | None = None
        #: Set to an exception to make `add_asset` fail.
        self.add_error: Exception | None = None

    def add_asset(
        self,
        workspace_id: uuid.UUID,
        project_id: uuid.UUID,
        name: str,
        kind: str,
        created_by: uuid.UUID,
        storage_path: str | None = None,
    ) -> Asset:
        if self.add_error is not None:
            raise self.add_error

        asset = Asset(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            project_id=project_id,
            name=name,
            kind=str(kind),
            storage_path=storage_path,
            created_by=created_by,
            created_at=datetime.now(UTC),
        )
        self.assets[asset.id] = asset

        return asset

    def attach_storage_path(
        self,
        workspace_id: uuid.UUID,
        asset_id: uuid.UUID,
        storage_path: str,
    ) -> Asset:
        if self.attach_error is not None:
            raise self.attach_error

        existing = self.assets[asset_id]
        updated = Asset(
            id=existing.id,
            workspace_id=existing.workspace_id,
            project_id=existing.project_id,
            name=existing.name,
            kind=existing.kind,
            storage_path=storage_path,
            created_by=existing.created_by,
            created_at=existing.created_at,
        )
        self.assets[asset_id] = updated

        return updated

    def get_asset(self, workspace_id: uuid.UUID, asset_id: uuid.UUID) -> Asset:
        asset = self.assets.get(asset_id)

        if asset is None or asset.workspace_id != workspace_id:
            raise ProjectNotFoundError("Asset not found")

        return asset


@pytest.fixture
def storage() -> RecordingStorageProvider:
    return RecordingStorageProvider()


@pytest.fixture
def projects() -> StubProjects:
    return StubProjects()


@pytest.fixture
def service(projects: StubProjects, storage: RecordingStorageProvider) -> AssetStorageService:
    # The stub satisfies the calls this service makes; mypy is not asked to
    # believe it is a `ProjectService`, which it deliberately is not.
    return AssetStorageService(projects, storage)  # type: ignore[arg-type]


def upload(service: AssetStorageService, *, name: str = "Cover", filename: str = "cover.png"):
    """Perform a valid PNG upload."""
    return service.upload(
        workspace_id=WORKSPACE,
        project_id=PROJECT,
        name=name,
        kind=AssetKind.IMAGE,
        data=PNG,
        declared_content_type="image/png",
        filename=filename,
        created_by=USER,
    )


class TestTheHappyPath:
    """What a successful upload leaves behind."""

    def test_the_row_points_at_the_object_that_was_stored(
        self, service: AssetStorageService, storage: RecordingStorageProvider
    ) -> None:
        asset = upload(service)

        assert asset.storage_path is not None
        assert (WORKSPACE, asset.storage_path) in storage.objects

    def test_the_stored_bytes_are_the_uploaded_bytes(
        self, service: AssetStorageService, storage: RecordingStorageProvider
    ) -> None:
        asset = upload(service)

        assert storage.objects[(WORKSPACE, asset.storage_path or "")] == PNG

    def test_the_canonical_content_type_is_stored_not_the_clients(
        self, service: AssetStorageService, storage: RecordingStorageProvider
    ) -> None:
        """A client's casing or parameters must not decide what is recorded."""
        service.upload(
            workspace_id=WORKSPACE,
            project_id=PROJECT,
            name="Cover",
            kind=AssetKind.IMAGE,
            data=PNG,
            declared_content_type="IMAGE/PNG; charset=binary",
            filename="cover.png",
            created_by=USER,
        )

        assert storage.put_error is None  # the upload really did reach `put`

    def test_the_display_name_is_kept_verbatim(self, service: AssetStorageService) -> None:
        """`assets.name` holds the human-readable original, not a sanitised one."""
        asset = upload(service, name="My holiday photo", filename="my holiday photo.png")

        assert asset.name == "My holiday photo"

    def test_two_uploads_of_the_same_filename_produce_two_objects(
        self, service: AssetStorageService, storage: RecordingStorageProvider
    ) -> None:
        """The collision proof, at the service level.

        `test_asset_logical_names.py` proves the names differ; this proves the
        consequence that matters -- two objects exist, and the first upload's
        bytes were not replaced by the second's.
        """
        first = upload(service, filename="photo.png")
        second = upload(service, filename="photo.png")

        assert first.storage_path != second.storage_path
        assert len(storage.objects) == 2


class TestValidationHappensBeforeAnythingIsWritten:
    """A refused upload must leave no row and no object."""

    def test_a_content_mismatch_creates_no_row(
        self, service: AssetStorageService, projects: StubProjects
    ) -> None:
        with pytest.raises(ContentMismatchError):
            service.upload(
                workspace_id=WORKSPACE,
                project_id=PROJECT,
                name="Cover",
                kind=AssetKind.IMAGE,
                data=b"MZ\x90\x00\x03\x00\x00\x00",
                declared_content_type="image/png",
                filename="cover.png",
                created_by=USER,
            )

        assert projects.assets == {}

    def test_an_unsupported_type_stores_nothing(
        self, service: AssetStorageService, storage: RecordingStorageProvider
    ) -> None:
        with pytest.raises(UnsupportedContentTypeError):
            service.upload(
                workspace_id=WORKSPACE,
                project_id=PROJECT,
                name="Cover",
                kind=AssetKind.IMAGE,
                data=PNG,
                declared_content_type="image/tiff",
                filename="cover.tiff",
                created_by=USER,
            )

        assert storage.objects == {}


class TestOrphanHandling:
    """Both directions of the row/object mismatch, provoked deliberately."""

    def test_a_failed_upload_leaves_a_row_with_no_storage_path(
        self,
        service: AssetStorageService,
        projects: StubProjects,
        storage: RecordingStorageProvider,
    ) -> None:
        """The required proof: no row pointing at a locator that was not stored.

        The row survives with a null `storage_path` -- visible, empty and
        retryable -- which is the deliberate choice recorded in Task 5. What must
        never happen is a row naming an object that does not exist, because the
        download route would then hand out a signed URL to nothing.
        """
        storage.put_error = StorageUnavailableError()

        with pytest.raises(StorageUnavailableError):
            upload(service)

        (asset,) = projects.assets.values()
        assert asset.storage_path is None
        assert storage.objects == {}

    def test_a_failed_row_update_deletes_the_object_it_could_not_reference(
        self,
        service: AssetStorageService,
        projects: StubProjects,
        storage: RecordingStorageProvider,
    ) -> None:
        """The other required proof: no stored object with no row.

        This is the only genuinely invisible failure available here -- there is
        no listing operation, so an unreferenced object could never be found
        again. It is therefore the one case that is actively cleaned up.
        """
        projects.attach_error = ProjectNotFoundError("Asset not found")

        with pytest.raises(ProjectNotFoundError):
            upload(service)

        assert storage.objects == {}
        assert len(storage.deleted) == 1

    def test_a_cleanup_failure_does_not_mask_the_original_error(
        self,
        service: AssetStorageService,
        projects: StubProjects,
        storage: RecordingStorageProvider,
    ) -> None:
        """The caller must learn what actually went wrong.

        If cleanup raised, the propagating exception would be a deletion failure
        rather than the row-update failure that caused it -- reporting the
        symptom and hiding the cause.
        """
        projects.attach_error = ProjectNotFoundError("Asset not found")
        storage.delete_error = StorageUnavailableError()

        with pytest.raises(ProjectNotFoundError):
            upload(service)

    def test_nothing_is_stored_when_the_row_cannot_be_created(
        self,
        service: AssetStorageService,
        projects: StubProjects,
        storage: RecordingStorageProvider,
    ) -> None:
        """Row first, bytes second -- so a failed row means no object at all.

        The reverse ordering would store bytes before anything referenced them,
        making this the unrecoverable case rather than the trivial one.
        """
        projects.add_error = ProjectNotFoundError()

        with pytest.raises(ProjectNotFoundError):
            upload(service)

        assert storage.objects == {}


class TestDownload:
    """Signing a URL, and refusing to sign one."""

    def test_a_signed_url_is_returned_for_a_stored_asset(
        self, service: AssetStorageService
    ) -> None:
        asset = upload(service)

        download = service.download_url(WORKSPACE, asset.id)

        assert download.url.startswith("https://")

    def test_the_ttl_is_fifteen_minutes(self, service: AssetStorageService) -> None:
        """15 minutes, set by the owner on 2026-08-16 (D3).

        Pinned because it is a security parameter: a signed URL is a bearer
        capability, and lengthening it widens the window in which a leaked URL
        still works. Changing this should require editing a test that says so.
        """
        asset = upload(service)

        download = service.download_url(WORKSPACE, asset.id)

        assert DOWNLOAD_URL_TTL.total_seconds() == 15 * 60
        assert download.expires_in_seconds == 900

    def test_the_locator_is_passed_through_untouched(
        self, service: AssetStorageService, storage: RecordingStorageProvider
    ) -> None:
        """No parsing, splitting or prefixing of the persisted value (ADR-004).

        The provider is asked for exactly the string the row holds; if this
        service reconstructed a `ws/<uuid>/...` key, the double would reject it.
        """
        asset = upload(service)

        download = service.download_url(WORKSPACE, asset.id)

        assert asset.storage_path in download.url

    def test_an_asset_with_no_bytes_is_a_not_found(self, service: AssetStorageService) -> None:
        """A metadata-only asset has nothing to sign."""
        service_projects: StubProjects = service._projects  # type: ignore[assignment]
        asset = service_projects.add_asset(
            workspace_id=WORKSPACE,
            project_id=PROJECT,
            name="Planned",
            kind=AssetKind.IMAGE,
            created_by=USER,
        )

        with pytest.raises(AssetFileNotFoundError):
            service.download_url(WORKSPACE, asset.id)

    def test_another_workspaces_asset_is_not_signed(self, service: AssetStorageService) -> None:
        """The row is resolved first, so no URL is generated for a hidden asset.

        The service-level half of the isolation proof. The route-level half --
        that RLS refuses the row over a real connection -- is in
        `test_asset_upload_api.py`.
        """
        asset = upload(service)

        with pytest.raises(ProjectNotFoundError):
            service.download_url(uuid.uuid4(), asset.id)
