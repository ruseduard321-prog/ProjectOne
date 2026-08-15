"""The real Cloudflare R2 signed-URL expiry proof.

**This is the mandatory integration proof STEP-27 requires**, and it is the one
thing `tests/test_storage_r2.py` structurally cannot establish: there,
`FakeS3Client` both issues the pseudo-presigned URL *and* implements the
verifier that decides it expired, so a pass demonstrates the double agreeing
with itself. Here the URL is signed by boto3 and the refusal comes from
Cloudflare.

## Why this is skipped by default

**Live vendor credentials must never become a routine CI dependency.** A test
suite that cannot run without a Cloudflare account is a suite that fails for
every contributor, on every fork, whenever a credential rotates -- and the usual
response to that is to weaken the test rather than fix the credential. So this
module skips unless storage is fully configured *and* the operator opts in with
`PROJECTONE_RUN_R2_INTEGRATION_TESTS=1`.

Two gates rather than one, deliberately: a developer who happens to have R2
configured for other work should not have their test run start creating and
deleting objects in a real bucket as a side effect.

## What it touches

One object, named with a random suffix, in the bucket the environment already
names. It is deleted in a `finally` block, and the deletion is verified. Nothing
else in the account is read, created or modified.
"""

from __future__ import annotations

import os
import time
import urllib.error
import urllib.request
import uuid

import pytest

from app.core.config import Settings
from app.storage.errors import ObjectNotFoundError
from app.storage.factory import build_storage_provider
from app.storage.providers.r2 import MIN_SIGNED_URL_EXPIRY

#: Opt-in switch. Absent means skip, so a normal `pytest` run never reaches R2.
_OPT_IN = "PROJECTONE_RUN_R2_INTEGRATION_TESTS"

#: How long to wait past the URL's stated lifetime before re-fetching. R2 is a
#: distributed system and its clock is not this machine's, so a fetch at exactly
#: expiry+0s is a race. The margin buys determinism; it does not weaken the
#: assertion, which is that an *expired* URL is refused.
_EXPIRY_MARGIN_SECONDS = 5


def _settings_or_skip() -> Settings:
    """Return live settings, or skip with the reason.

    Skipping is the correct outcome without credentials -- a failure here would
    report a missing Cloudflare account as a defect in ProjectOne.
    """
    if os.environ.get(_OPT_IN) != "1":
        pytest.skip(
            f"R2 integration proof is opt-in: set {_OPT_IN}=1 to run it against "
            "a real bucket. Never enable this in shared CI."
        )

    settings = Settings()  # type: ignore[call-arg]
    if not settings.storage_is_configured:
        pytest.skip("R2 is not configured in this environment")

    return settings


def _http_get(url: str) -> tuple[int, bytes]:
    """Perform a real HTTP GET and return the status and body.

    Deliberately **not** boto3. The point of a presigned URL is that anything
    which speaks HTTP can use it without credentials -- a browser, a CDN, a
    video player. Fetching it through the SDK that signed it would test a
    narrower thing than the one users depend on.

    A 4xx arrives as `HTTPError`, which is a response rather than a transport
    failure, so it is unwrapped into a status rather than raised.
    """
    request = urllib.request.Request(url, method="GET")  # noqa: S310 - https URL from R2
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            return int(response.status), response.read()
    except urllib.error.HTTPError as error:
        return int(error.code), error.read()


@pytest.mark.integration
class TestRealR2SignedUrlExpiry:
    """Signed-URL expiry, proven against Cloudflare R2 itself."""

    def test_a_real_presigned_url_works_then_is_refused_after_expiry(self) -> None:
        """**The STEP-27 proof.** Issue, use, wait, use again, and be refused.

        Every step is real: boto3 signs the URL, R2 stores the object, and the
        two fetches are ordinary HTTP requests carrying no credentials. The
        refusal at the end comes from Cloudflare evaluating the signature's
        expiry, which is the only party whose opinion actually matters.
        """
        settings = _settings_or_skip()
        provider = build_storage_provider(settings)

        workspace_id = uuid.uuid4()
        logical_name = f"step27-expiry-proof-{uuid.uuid4().hex}.txt"
        payload = b"STEP-27 disposable expiry proof object"

        stored = provider.put(workspace_id, logical_name, payload, "text/plain")
        assert stored.locator == logical_name

        try:
            # Minimum supported lifetime, so the wait is short and the window
            # being tested is unambiguous.
            url = provider.signed_url(workspace_id, logical_name, MIN_SIGNED_URL_EXPIRY)

            # --- before expiry: R2 serves the object -----------------------
            status, body = _http_get(url)
            assert status == 200, f"a valid presigned URL should serve the object, got {status}"
            assert body == payload

            # --- wait past the stated lifetime -----------------------------
            time.sleep(MIN_SIGNED_URL_EXPIRY.total_seconds() + _EXPIRY_MARGIN_SECONDS)

            # --- after expiry: the SAME url is refused ---------------------
            status, body = _http_get(url)
            assert status in (400, 403), f"R2 should refuse an expired presigned URL, got {status}"
            # R2 says why, and it is the expiry rather than a missing object --
            # a 404 here would mean the object vanished and the test proved
            # nothing about signatures.
            assert b"Expired" in body or b"AccessDenied" in body or b"expired" in body

            # The object itself is untouched: expiry invalidates the URL, not
            # the data behind it.
            assert provider.get(workspace_id, logical_name) == payload

        finally:
            # Disposable means disposed of, whatever happened above.
            provider.delete(workspace_id, logical_name)

        # --- cleanup verified, not assumed ---------------------------------
        with pytest.raises(ObjectNotFoundError):
            provider.get(workspace_id, logical_name)
