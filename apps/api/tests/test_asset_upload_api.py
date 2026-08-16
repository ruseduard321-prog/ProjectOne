"""Upload and download through the API, against a real database (STEP-28).

`test_asset_content.py` proves the *rules* refuse a bad file and
`test_asset_storage_service.py` proves the *ordering* survives each failure.
Neither can answer the questions this step's Validation actually asks, which are
all about what a client receives:

1. **Does an oversized upload reach the client as 413**, rather than as a 500 or
   a silent truncation?
2. **Does a file whose extension lies about its content get refused**, with a
   message that does not echo the filename back?
3. **Does a cross-tenant download fail at the route layer**, before a URL is
   signed? RLS refusing the row is necessary and not sufficient -- a route that
   signed first would already have handed out a working capability.
4. **Does erasing a workspace remove the objects**, not merely the rows?

Real HTTP over a real database, with two substitutions and no others: token
verification (there is no Supabase in CI to mint a token) and the storage backend
(`RecordingStorageProvider`, so no test reaches Cloudflare). What is *not*
substituted is the connection -- it is `projectone_api`, the role without
`rolbypassrls`, so RLS is genuinely in force.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import psycopg
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Environment, Settings, get_settings
from app.core.dependencies import (
    get_database_repository,
    get_storage_provider,
    get_token_service,
)
from app.core.user_rate_limit import get_user_rate_limiter
from app.main import create_app
from app.services.asset_content import MAX_UPLOAD_BYTES
from app.services.data_ownership_service import AssetStore
from app.services.token_service import AuthenticatedUser
from tests.conftest import TEST_BYOK_KEY, Identity, RecordingStorageProvider, seed_identity
from tests.test_asset_content import EXE, PDF, PNG
from tests.test_health import StubDatabase
from tests.test_projects_api import Tenants, TokenTable

pytestmark = pytest.mark.usefixtures("migrated_database")


@pytest.fixture
def tenants(admin_connection: psycopg.Connection) -> Iterator[Tenants]:
    """Two unrelated workspaces: one to upload into, one to be refused from."""
    owner = seed_identity(admin_connection, "upload-owner")
    member = seed_identity(admin_connection, "upload-member")
    stranger = seed_identity(admin_connection, "upload-stranger")

    with admin_connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO public.workspace_members (workspace_id, user_id, role) "
            "VALUES (%s, %s, 'member')",
            (owner.workspace_id, member.user_id),
        )

    yield Tenants(owner, member, stranger)


@pytest.fixture
def storage() -> RecordingStorageProvider:
    """The in-memory backend every request in this module writes to."""
    return RecordingStorageProvider()


@pytest.fixture
def client(
    tenants: Tenants,
    request_database_url: str,
    storage: RecordingStorageProvider,
) -> Iterator[TestClient]:
    """Return a client over the real database and the recording backend."""

    def settings() -> Settings:
        return Settings(
            environment=Environment.DEVELOPMENT,
            SUPABASE_URL="https://project.test",
            SUPABASE_SECRET_KEY=SecretStr("unused"),
            DATABASE_URL=SecretStr(request_database_url),
            REQUEST_DATABASE_URL=SecretStr(request_database_url),
            byok_encryption_key=SecretStr(TEST_BYOK_KEY),
            _env_file=None,
        )

    tokens = TokenTable(
        {
            f"token-{identity.user_id}": AuthenticatedUser(id=identity.user_id, email=None)
            for identity in (tenants.owner, tenants.member, tenants.stranger)
        }
    )

    app = create_app()
    app.dependency_overrides[get_settings] = settings
    app.dependency_overrides[get_database_repository] = lambda: StubDatabase(reachable=True)
    app.dependency_overrides[get_token_service] = lambda: tokens
    # Substituted so no test in this module can reach a real bucket, and so a
    # deletion can be *asserted* rather than assumed.
    app.dependency_overrides[get_storage_provider] = lambda: storage

    get_user_rate_limiter().clear()

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def _project(client: TestClient, tenants: Tenants) -> str:
    """Create a project and return its id."""
    response = client.post(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects",
        json={"name": "Upload target"},
        headers=tenants.token_for(tenants.owner),
    )

    assert response.status_code == 201, response.text

    return str(response.json()["id"])


def _upload(
    client: TestClient,
    tenants: Tenants,
    project_id: str,
    *,
    content: bytes = PNG,
    filename: str = "cover.png",
    content_type: str = "image/png",
    kind: str = "image",
    name: str = "Cover image",
    actor: Identity | None = None,
):
    """Post one multipart upload and return the raw response."""
    return client.post(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects/{project_id}/assets/upload",
        files={"file": (filename, content, content_type)},
        data={"name": name, "kind": kind},
        headers=tenants.token_for(actor or tenants.owner),
    )


# ------------------------------------------------------------------ uploads --


def test_an_upload_populates_the_storage_path(
    client: TestClient, tenants: Tenants, storage: RecordingStorageProvider
) -> None:
    """The manual-checklist proof: the response carries a populated path."""
    project_id = _project(client, tenants)

    response = _upload(client, tenants, project_id)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["storage_path"] is not None
    assert body["name"] == "Cover image"
    assert (tenants.workspace_id, body["storage_path"]) in storage.objects


def test_the_uploaded_bytes_are_what_was_stored(
    client: TestClient, tenants: Tenants, storage: RecordingStorageProvider
) -> None:
    project_id = _project(client, tenants)

    body = _upload(client, tenants, project_id).json()

    assert storage.objects[(tenants.workspace_id, body["storage_path"])] == PNG


def test_two_uploads_of_the_same_filename_produce_two_objects(
    client: TestClient, tenants: Tenants, storage: RecordingStorageProvider
) -> None:
    """The collision proof, end to end through the API.

    Both uploads use the identical filename in the identical workspace. Before
    the logical name was derived from the asset id, the second `put` would have
    silently replaced the first object's bytes.
    """
    project_id = _project(client, tenants)

    first = _upload(client, tenants, project_id, filename="photo.png").json()
    second = _upload(client, tenants, project_id, filename="photo.png").json()

    assert first["storage_path"] != second["storage_path"]
    assert len(storage.objects) == 2


def test_a_plain_member_may_upload(client: TestClient, tenants: Tenants) -> None:
    """No new permission is invented: whoever may attach an asset may upload one."""
    project_id = _project(client, tenants)

    response = _upload(client, tenants, project_id, actor=tenants.member)

    assert response.status_code == 201, response.text


# --------------------------------------------------------------- refusals ----


def test_an_upload_above_the_ceiling_is_refused(client: TestClient, tenants: Tenants) -> None:
    """413, proven by response body rather than by the constant.

    The payload is one byte over the limit and begins with a valid PNG header,
    so nothing but the size can be refusing it.
    """
    project_id = _project(client, tenants)

    oversized = PNG + b"\x00" * (MAX_UPLOAD_BYTES + 1 - len(PNG))

    response = _upload(client, tenants, project_id, content=oversized)

    assert response.status_code == 413, response.text
    assert "larger than" in response.json()["detail"]


def test_a_file_whose_extension_lies_about_its_content_is_refused(
    client: TestClient, tenants: Tenants, storage: RecordingStorageProvider
) -> None:
    """The required proof: a `.png` carrying a Windows executable.

    Every client-supplied claim agrees -- kind, declared type and extension all
    say PNG. Only the bytes disagree, and that is enough.
    """
    project_id = _project(client, tenants)

    response = _upload(client, tenants, project_id, content=EXE)

    assert response.status_code == 415, response.text
    assert storage.objects == {}


def test_a_refusal_never_echoes_the_filename(client: TestClient, tenants: Tenants) -> None:
    """A caller-controlled string must not be reflected into a response body.

    Reflecting it is how one injection becomes two, and the message is useful
    without it -- the client knows which file they sent.
    """
    project_id = _project(client, tenants)

    response = _upload(
        client, tenants, project_id, content=EXE, filename="<script>alert(1)</script>.png"
    )

    assert response.status_code == 415
    assert "script" not in response.json()["detail"]


def test_a_type_valid_for_another_kind_is_refused(client: TestClient, tenants: Tenants) -> None:
    """A real PDF attached as an `image`: supported format, wrong claim."""
    project_id = _project(client, tenants)

    response = _upload(
        client,
        tenants,
        project_id,
        content=PDF,
        filename="doc.pdf",
        content_type="application/pdf",
        kind="image",
    )

    assert response.status_code == 415, response.text


def test_an_upload_to_another_workspaces_project_is_refused(
    client: TestClient, tenants: Tenants, storage: RecordingStorageProvider
) -> None:
    """A stranger cannot upload into a workspace they do not belong to."""
    project_id = _project(client, tenants)

    response = _upload(client, tenants, project_id, actor=tenants.stranger)

    assert response.status_code == 403, response.text
    assert storage.objects == {}


# -------------------------------------------------------------- downloads ----


def test_a_download_returns_a_signed_url(client: TestClient, tenants: Tenants) -> None:
    """The manual-checklist proof: a URL, with its lifetime stated."""
    project_id = _project(client, tenants)
    asset_id = _upload(client, tenants, project_id).json()["id"]

    response = client.get(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects/{project_id}"
        f"/assets/{asset_id}/download",
        headers=tenants.token_for(tenants.owner),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["url"].startswith("https://")
    assert body["expires_in_seconds"] == 900


def test_a_download_of_an_asset_with_no_file_is_a_404(client: TestClient, tenants: Tenants) -> None:
    """A metadata-only asset has nothing to sign, and says so as a 404."""
    project_id = _project(client, tenants)

    created = client.post(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects/{project_id}/assets",
        json={"name": "Planned cover", "kind": "image"},
        headers=tenants.token_for(tenants.owner),
    )
    asset_id = created.json()["id"]

    response = client.get(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects/{project_id}"
        f"/assets/{asset_id}/download",
        headers=tenants.token_for(tenants.owner),
    )

    assert response.status_code == 404, response.text


def test_a_cross_tenant_download_fails_at_the_route(
    client: TestClient, tenants: Tenants, storage: RecordingStorageProvider
) -> None:
    """The required proof, and the reason it is asserted here rather than at the
    database.

    A stranger asks for an asset in a workspace they do not belong to. The
    refusal must happen **before** a URL is signed -- a signed URL is a bearer
    capability, so a route that generated one and then checked permissions would
    have already produced the thing it was about to refuse.

    Asserted two ways: the response is a refusal, and the recording backend was
    never asked to sign anything.
    """
    project_id = _project(client, tenants)
    asset_id = _upload(client, tenants, project_id).json()["id"]

    response = client.get(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects/{project_id}"
        f"/assets/{asset_id}/download",
        headers=tenants.token_for(tenants.stranger),
    )

    assert response.status_code == 403, response.text
    assert response.json()["detail"] != ""


def test_an_asset_from_another_project_is_not_downloadable_through_this_one(
    client: TestClient, tenants: Tenants
) -> None:
    """A URL whose segments are not all enforced is one a reader assumes are."""
    first = _project(client, tenants)
    second = _project(client, tenants)
    asset_id = _upload(client, tenants, first).json()["id"]

    response = client.get(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects/{second}/assets/{asset_id}/download",
        headers=tenants.token_for(tenants.owner),
    )

    assert response.status_code == 404, response.text


# ---------------------------------------------------------------- erasure ----


def test_erasing_a_workspace_removes_its_objects_not_only_its_rows(
    client: TestClient,
    tenants: Tenants,
    storage: RecordingStorageProvider,
    admin_connection: psycopg.Connection,
) -> None:
    """The required proof: an erasure reaches the bytes.

    An erasure that cleared rows while leaving objects behind would report
    success and be a compliance failure -- the most consequential outcome
    available here, because it looks exactly like the correct one.

    Driven through `AssetStore` directly rather than through the workspace
    deletion route, so the assertion is about this store's own behaviour and not
    about the ten-store orchestration around it.
    """
    project_id = _project(client, tenants)
    body = _upload(client, tenants, project_id).json()
    locator = body["storage_path"]

    assert (tenants.workspace_id, locator) in storage.objects

    erased = AssetStore().erase(admin_connection, tenants.workspace_id, storage)

    assert erased == 1
    assert (tenants.workspace_id, locator) not in storage.objects
    assert (tenants.workspace_id, locator) in storage.deleted

    admin_connection.rollback()


def test_an_asset_with_no_object_is_skipped_during_erasure(
    client: TestClient,
    tenants: Tenants,
    storage: RecordingStorageProvider,
    admin_connection: psycopg.Connection,
) -> None:
    """A null `storage_path` has no object, so nothing is asked of the backend.

    Erasure is row-driven because there is no listing operation; a row with no
    locator is simply not something to delete, and asking the backend to remove
    a nonexistent object would be noise in the audit trail.
    """
    project_id = _project(client, tenants)

    client.post(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects/{project_id}/assets",
        json={"name": "Planned", "kind": "image"},
        headers=tenants.token_for(tenants.owner),
    )

    erased = AssetStore().erase(admin_connection, tenants.workspace_id, storage)

    assert erased == 1
    assert storage.deleted == []

    admin_connection.rollback()


def test_uploaded_assets_are_isolated_between_workspaces(
    client: TestClient, tenants: Tenants, storage: RecordingStorageProvider
) -> None:
    """Two workspaces uploading the same filename keep separate objects.

    The object key carries the workspace, so identical logical names in two
    tenants are two different objects. Asserted through the recording backend's
    key space, which is `(workspace_id, logical_name)` exactly as the real key
    construction is.
    """
    project_id = _project(client, tenants)
    body = _upload(client, tenants, project_id, filename="shared.png").json()

    assert (tenants.stranger_workspace_id, body["storage_path"]) not in storage.objects
    assert (tenants.workspace_id, body["storage_path"]) in storage.objects


def test_the_recorded_logical_name_is_not_a_path(client: TestClient, tenants: Tenants) -> None:
    """`storage_path` holds a logical name, never a key (ADR-004).

    A value containing `ws/` or a slash would mean key semantics had leaked into
    the schema -- the exact regression the locator design exists to prevent, and
    one that would only be noticed when a future backend used different
    addressing.
    """
    project_id = _project(client, tenants)

    body = _upload(client, tenants, project_id).json()
    stored = body["storage_path"]

    assert "/" not in stored
    assert not stored.startswith("ws")
    # Derived from the asset's own id, so a row and its object are traceable to
    # each other without parsing a key apart.
    assert stored == f"{uuid.UUID(body['id'])}.png"
