"""STEP-28's upload, download and erasure paths, against real Cloudflare R2.

**The proof `test_asset_upload_api.py` structurally cannot give.** There, and in
every other test of this step, `RecordingStorageProvider` stands in for the
backend — a double I wrote, to match my reading of the contract. A pass
therefore shows the code agreeing with my reading. It does not show R2 agreeing
with either.

Here nothing is doubled. boto3 signs, Cloudflare stores, and the download is an
ordinary HTTP request carrying no credentials.

## What this closes that [[STEP-27 Storage Provider Abstraction]]'s proof does not

`test_storage_r2_integration.py` calls `provider.put`/`signed_url`/`get`/`delete`
directly, with a logical name **it invents itself**. Everything STEP-28 added
sits above that call and has never touched a real backend:

- the logical name is derived from a **UUID PostgreSQL issued**, not a literal;
- it is written into `assets.storage_path`, read back in a **later request**, and
  handed to `signed_url` — a four-hop round trip STEP-27 had no database for;
- `AssetStore.erase` reads real rows and deletes real objects, a loop that only
  existed from STEP-28 onward.

If `derive_logical_name` produced something R2 rejected, or the column altered
what came back, or the workspace id reached the provider from the wrong source,
**every existing test would still pass** — the double accepts what the real
backend might not.

## Why three gates

1. `PROJECTONE_RUN_R2_INTEGRATION_TESTS=1` — live vendor credentials must never
   become a routine CI dependency. A suite that fails on every fork when a
   credential rotates gets weakened rather than fixed.
2. R2 fully configured.
3. **A real PostgreSQL**, which STEP-27's proof does not need. The round trip
   through `assets.storage_path` is the point, so a database is not optional
   here.

Consequence, stated rather than discovered: this module runs on a developer
machine with both, and **nowhere else**. CI has neither, deliberately. These two
Validation items stay human-gated — re-proven when someone runs them, unlike the
automated proofs that re-run on every Pull Request.

## What it touches

Objects under `ws/<random-uuid>/`, in `projectone-dev` and no other bucket. Every
one is deleted in fixture teardown and the deletion **verified**; a leak fails
the run loudly rather than passing quietly.
"""

from __future__ import annotations

import os
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Iterator

import psycopg
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Environment, Settings, get_settings
from app.core.dependencies import get_database_repository, get_token_service
from app.core.user_rate_limit import get_user_rate_limiter
from app.main import create_app
from app.services.asset_storage_service import DOWNLOAD_URL_TTL
from app.services.data_ownership_service import AssetStore
from app.services.token_service import AuthenticatedUser
from app.storage.errors import ObjectNotFoundError
from app.storage.factory import build_storage_provider
from app.storage.provider import StorageProvider
from tests.conftest import TEST_BYOK_KEY, seed_identity
from tests.test_asset_content import PNG
from tests.test_health import StubDatabase
from tests.test_projects_api import Tenants, TokenTable

#: Opt-in switch, shared with STEP-27's proof rather than duplicated. One switch
#: means "this run may reach Cloudflare", which is the property an operator
#: actually reasons about.
_OPT_IN = "PROJECTONE_RUN_R2_INTEGRATION_TESTS"

#: The only bucket this module will write to.
#:
#: **A hard refusal, not a preference.** A test that writes to whichever bucket
#: happens to be configured is one production credential away from writing to
#: production. Pointed anywhere else, this module fails loudly instead of
#: proceeding — the operator asked for a live run against a bucket we will not
#: touch, and skipping would understate that.
EXPECTED_BUCKET = "projectone-dev"

#: What the download route promises. Asserted against the URL R2 actually signs.
EXPECTED_TTL_SECONDS = int(DOWNLOAD_URL_TTL.total_seconds())

pytestmark = pytest.mark.integration


# --------------------------------------------------------------- the gates --


@pytest.fixture(scope="module")
def live_settings() -> Settings:
    """Return settings pointed at the real bucket, or skip.

    **Not necessarily the first gate to fire**, and that is worth knowing before
    reading a skip message. `migrated_database` and `request_database_url` are
    session-scoped, so pytest resolves them ahead of this module-scoped fixture:
    on a machine with no test database the skip names
    `PROJECTONE_TEST_DATABASE_URL`, whichever gate the reader had in mind.

    Harmless, because both messages name a genuinely missing prerequisite and
    neither reaches Cloudflare. Recorded rather than fixed: forcing an order
    across scopes would mean fighting pytest's resolution for a cosmetic gain in
    one of two equally-correct messages.
    """
    if os.environ.get(_OPT_IN) != "1":
        pytest.skip(
            f"STEP-28 live storage proof is opt-in: set {_OPT_IN}=1 to run it "
            "against a real bucket. Never enable this in shared CI."
        )

    settings = Settings()  # type: ignore[call-arg]

    if not settings.storage_is_configured:
        pytest.skip("R2 is not configured in this environment")

    if settings.r2_bucket != EXPECTED_BUCKET:
        pytest.fail(
            f"Refusing to run: this module only writes to {EXPECTED_BUCKET!r}, but the "
            f"environment names a different bucket. Point PROJECTONE_R2_BUCKET at the "
            "development bucket, or do not opt in."
        )

    return settings


@pytest.fixture(scope="module")
def live_provider(live_settings: Settings) -> StorageProvider:
    """Return a provider built independently of the one the app uses.

    Deliberately a second instance. The application builds its own through
    `get_storage_provider`, and asserting through *this* one means a test's
    verification does not travel the same object as the behaviour it checks.
    """
    return build_storage_provider(live_settings)


@pytest.fixture
def stored_objects(live_provider: StorageProvider) -> Iterator[list[tuple[uuid.UUID, str]]]:
    """Track every object created, and remove them all afterwards.

    **Teardown rather than per-test `finally` blocks**, which is a deliberate
    departure from STEP-27's proof. That one has two gaps this shape closes by
    construction: an assertion sitting outside its `try` (an object created and
    then leaked if it ever fires), and cleanup that runs but goes unverified
    when the test fails. Fixture teardown runs on pass, on failure and on error,
    and it runs after everything.

    Deletion is **verified, not assumed**, and a leak fails the run. An object
    left in a real bucket must never be a silent outcome — nothing can enumerate
    the bucket later to find it (ADR-004), so the log line here is the only
    record that would exist.
    """
    created: list[tuple[uuid.UUID, str]] = []

    yield created

    leaked: list[str] = []

    for workspace_id, locator in created:
        try:
            # Idempotent, so an object an erasure test already removed costs
            # nothing and is not an error.
            live_provider.delete(workspace_id, locator)
        except Exception as error:  # noqa: BLE001 - reported below, never masked
            leaked.append(f"{workspace_id}/{locator}: delete failed ({type(error).__name__})")
            continue

        try:
            live_provider.get(workspace_id, locator)
        except ObjectNotFoundError:
            continue
        except Exception as error:  # noqa: BLE001 - reported below
            leaked.append(f"{workspace_id}/{locator}: verify failed ({type(error).__name__})")
            continue

        leaked.append(f"{workspace_id}/{locator}: still readable after delete")

    if leaked:
        pytest.fail(
            "Live objects were left in "
            + EXPECTED_BUCKET
            + " and must be removed by hand:\n  "
            + "\n  ".join(leaked)
        )


# ------------------------------------------------------------ the fixtures --


@pytest.fixture
def tenants(live_settings: Settings, admin_connection: psycopg.Connection) -> Iterator[Tenants]:
    """Seed one workspace with an owner and a member, plus an unrelated one."""
    owner = seed_identity(admin_connection, "live-owner")
    member = seed_identity(admin_connection, "live-member")
    stranger = seed_identity(admin_connection, "live-stranger")

    with admin_connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO public.workspace_members (workspace_id, user_id, role) "
            "VALUES (%s, %s, 'member')",
            (owner.workspace_id, member.user_id),
        )

    yield Tenants(owner, member, stranger)


@pytest.fixture
def client(
    live_settings: Settings,
    request_database_url: str,
    tenants: Tenants,
) -> Iterator[TestClient]:
    """Return a client over the real database **and the real storage backend**.

    The single line that makes this module live is the one that is *absent*:
    `get_storage_provider` is **not** overridden. Every other test of this step
    substitutes `RecordingStorageProvider` there; here the application builds its
    own provider from the process environment and talks to Cloudflare.

    Token verification is still substituted — there is no Supabase to mint a
    token — and the R2 values are copied onto the settings override so nothing
    in the application sees a configuration that disagrees with the backend it
    is actually using.
    """

    def settings() -> Settings:
        return Settings(
            environment=Environment.DEVELOPMENT,
            SUPABASE_URL="https://project.test",
            SUPABASE_SECRET_KEY=SecretStr("unused"),
            DATABASE_URL=SecretStr(request_database_url),
            REQUEST_DATABASE_URL=SecretStr(request_database_url),
            byok_encryption_key=SecretStr(TEST_BYOK_KEY),
            r2_account_id=live_settings.r2_account_id,
            r2_bucket=live_settings.r2_bucket,
            r2_access_key_id=live_settings.r2_access_key_id,
            r2_secret_access_key=live_settings.r2_secret_access_key,
            _env_file=None,
        )

    tokens = TokenTable(
        {
            f"token-{identity.user_id}": AuthenticatedUser(id=identity.user_id, email=None)
            for identity in (tenants.owner, tenants.member, tenants.stranger)
        }
    )

    # Cleared so the provider is rebuilt from the environment this module
    # verified, rather than reused from whatever an earlier test cached.
    get_settings.cache_clear()

    app = create_app()
    app.dependency_overrides[get_settings] = settings
    app.dependency_overrides[get_database_repository] = lambda: StubDatabase(reachable=True)
    app.dependency_overrides[get_token_service] = lambda: tokens

    get_user_rate_limiter().clear()

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    get_settings.cache_clear()


# ------------------------------------------------------------- the helpers --


def _project(client: TestClient, tenants: Tenants) -> str:
    """Create a project and return its id."""
    response = client.post(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects",
        json={"name": "Live storage proof"},
        headers=tenants.token_for(tenants.owner),
    )

    assert response.status_code == 201, response.text

    return str(response.json()["id"])


def _upload(
    client: TestClient,
    tenants: Tenants,
    project_id: str,
    tracked: list[tuple[uuid.UUID, str]],
) -> dict[str, str]:
    """Upload a real PNG through the API and register the object for cleanup.

    **Registration happens inside this helper**, immediately after the locator
    is known, so there is no window in which an object exists untracked. A
    caller that registered afterwards could error in between and leak.
    """
    response = client.post(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects/{project_id}/assets/upload",
        files={"file": ("live-proof.png", PNG, "image/png")},
        data={"name": "Live proof image", "kind": "image"},
        headers=tenants.token_for(tenants.owner),
    )

    assert response.status_code == 201, response.text
    body: dict[str, str] = response.json()

    tracked.append((tenants.workspace_id, body["storage_path"]))

    return body


def _download(
    client: TestClient, tenants: Tenants, project_id: str, asset_id: str
) -> dict[str, str]:
    """Ask the API for a signed URL."""
    response = client.get(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects/{project_id}"
        f"/assets/{asset_id}/download",
        headers=tenants.token_for(tenants.owner),
    )

    assert response.status_code == 200, response.text

    result: dict[str, str] = response.json()

    return result


def _http_get(url: str) -> tuple[int, bytes]:
    """Fetch a URL over plain HTTP, carrying no credentials.

    Deliberately **not** boto3. The point of a signed URL is that anything
    speaking HTTP can use it without credentials — a browser, a CDN, a video
    player. Fetching it through the SDK that signed it would prove a narrower
    thing than the one users depend on.
    """
    request = urllib.request.Request(url, method="GET")  # noqa: S310 - https URL from R2
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            return int(response.status), response.read()
    except urllib.error.HTTPError as error:
        return int(error.code), error.read()


# --------------------------------------------------------------- the proofs --


def test_an_uploaded_object_is_retrievable_through_its_signed_url(
    client: TestClient,
    tenants: Tenants,
    stored_objects: list[tuple[uuid.UUID, str]],
) -> None:
    """**Validation item 4**, end to end and with nothing doubled.

    Four hops STEP-27's proof never made, in one request each: the route stores
    the bytes, the derived logical name is persisted, a *later* request reads it
    back out of the column, and R2 signs a URL for it. The final fetch carries
    no credentials, which is what a browser does.

    A defect anywhere in that chain — a logical name R2 rejects, a locator the
    column alters, a workspace id taken from the wrong source — passes every
    other test of this step and fails here.
    """
    project_id = _project(client, tenants)

    uploaded = _upload(client, tenants, project_id, stored_objects)
    assert uploaded["storage_path"], "the upload route must populate storage_path"

    download = _download(client, tenants, project_id, uploaded["id"])

    status, body = _http_get(download["url"])

    assert status == 200, f"R2 should serve a valid signed URL, got {status}: {body!r}"
    assert body == PNG, "the bytes R2 returned are not the bytes that were uploaded"


def test_the_signed_url_carries_the_fifteen_minute_lifetime(
    client: TestClient,
    tenants: Tenants,
    stored_objects: list[tuple[uuid.UUID, str]],
) -> None:
    """The 15-minute decision (D3) reaches the signature R2 evaluates.

    **This proves ProjectOne sends 900 seconds; it does not prove R2 enforces
    expiry.** That was established by STEP-27's proof, which waits out a
    one-second URL and is refused by Cloudflare. Repeating that here at fifteen
    minutes would mean a test that sleeps a quarter of an hour to re-establish
    something already known.

    So the gap this closes is the one between the two: that *this* call site
    passes the value it claims to, all the way into the signature, rather than
    the response body saying 900 while the URL was signed for something else.
    """
    project_id = _project(client, tenants)
    uploaded = _upload(client, tenants, project_id, stored_objects)

    download = _download(client, tenants, project_id, uploaded["id"])

    assert int(download["expires_in_seconds"]) == EXPECTED_TTL_SECONDS

    query = urllib.parse.parse_qs(urllib.parse.urlparse(download["url"]).query)
    signed_expiry = query.get("X-Amz-Expires")

    assert signed_expiry is not None, (
        "the signed URL carries no X-Amz-Expires parameter, so the lifetime the "
        "response advertises cannot be checked against the one R2 will enforce"
    )
    assert int(signed_expiry[0]) == EXPECTED_TTL_SECONDS, (
        f"the API advertises {EXPECTED_TTL_SECONDS}s but the URL is signed for "
        f"{signed_expiry[0]}s — a client would trust the wrong number"
    )


def test_erasing_the_workspace_makes_the_object_unreachable(
    client: TestClient,
    tenants: Tenants,
    live_provider: StorageProvider,
    admin_connection: psycopg.Connection,
    stored_objects: list[tuple[uuid.UUID, str]],
) -> None:
    """**Validation item 5**: the object stops existing, not merely the row.

    `AssetStore.erase` gained its `StorageProvider` in STEP-28 and its
    row-driven deletion loop has only ever run against an in-memory double —
    one written to match my own reading of the contract, which is exactly the
    agreement a live proof exists to break.

    The object's existence is confirmed **before** the erasure so the assertion
    afterwards means something: without that, a test where the upload silently
    stored nothing would pass for the wrong reason.

    An erasure that clears rows while leaving bytes behind is the most
    consequential failure this step can have, precisely because it looks exactly
    like the correct one (CLAUDE.md §16).
    """
    project_id = _project(client, tenants)
    uploaded = _upload(client, tenants, project_id, stored_objects)
    locator = uploaded["storage_path"]

    assert live_provider.get(tenants.workspace_id, locator) == PNG, (
        "the object must exist before erasure, or the assertion below proves nothing"
    )

    erased = AssetStore().erase(admin_connection, tenants.workspace_id, live_provider)

    assert erased == 1, f"expected one asset row erased, got {erased}"

    with pytest.raises(ObjectNotFoundError):
        live_provider.get(tenants.workspace_id, locator)

    admin_connection.rollback()
