"""The Cloudflare R2 adapter, reached through R2's S3-compatible API.

**Everything vendor-specific in ProjectOne's storage layer lives in this file.**
`boto3`, `botocore`, the endpoint URL, the bucket name and R2's error codes stop
here; callers above see `bytes`, `str`, `StoredObject` and the error hierarchy in
`app.storage.errors` ([[ADR-004 Object Storage Provider and Tenant-Safe Key
Construction]] §3, asserted by `tests/test_storage_boundary.py`).

## Why boto3 against the S3-compatible API

Cloudflare's own presigned-URL documentation lists Boto3 as a supported client
for R2, and the S3 API is what makes the adapter portable: the same shape reaches
AWS S3, MinIO and Backblaze, so a future second adapter is a configuration change
rather than a rewrite. That portability is the point of the boundary, and picking
a Cloudflare-proprietary client would have quietly given it up.

## Configuration facts, verified against Cloudflare documentation

- **Endpoint:** `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`.
- **Region:** R2 buckets are region `auto`. Boto3 requires *some* region, so
  `auto` is passed explicitly rather than left to the environment, where an
  inherited `AWS_DEFAULT_REGION` would otherwise decide it.
- **Presigned URL lifetime:** 1 second to 7 days (604,800 seconds). Enforced
  here, so an out-of-range request fails at the call rather than producing a URL
  R2 rejects later.

## One private bucket, not one per workspace

Workspace separation is expressed in the **key**, not in the bucket
([[ADR-004 Object Storage Provider and Tenant-Safe Key Construction]] §6). No
object is public; bytes reach a browser through a presigned URL with a bounded
lifetime.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from app.storage.errors import (
    ObjectNotFoundError,
    StorageAccessDeniedError,
    StorageUnavailableError,
)
from app.storage.keys import build_object_key
from app.storage.provider import StorageProvider, StoredObject

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Mapping

#: R2's permitted presigned-URL lifetime, from Cloudflare's documentation.
#: Enforced rather than trusted: a caller asking for eight days should get an
#: error here, not a URL that silently fails when someone opens it.
MIN_SIGNED_URL_EXPIRY = timedelta(seconds=1)
MAX_SIGNED_URL_EXPIRY = timedelta(days=7)

#: R2 buckets are region `auto`.
R2_REGION = "auto"

#: Error codes meaning "no such object". Both appear depending on whether the
#: caller had permission to know the difference, and both mean the same thing to
#: a caller of this adapter.
_NOT_FOUND_CODES = frozenset({"NoSuchKey", "404", "NotFound"})

#: Error codes meaning the credential was refused.
_ACCESS_DENIED_CODES = frozenset(
    {"AccessDenied", "InvalidAccessKeyId", "SignatureDoesNotMatch", "403"}
)


class R2StorageProvider(StorageProvider):
    """Cloudflare R2, behind the vendor-neutral `StorageProvider` contract.

    The client is injected rather than constructed here. That keeps this class
    testable against a stand-in S3 client with no network and no Cloudflare
    account, and it keeps credential assembly in one place
    (`app.storage.factory`) instead of spread across every construction site.
    """

    def __init__(self, client: Any, bucket: str) -> None:  # noqa: ANN401
        """Store the S3-compatible client and the bucket every key lives in.

        Args:
            client: A boto3 S3 client configured for R2. Typed `Any` because
                boto3 generates its clients at runtime and exposes no static
                type for them -- and, more importantly, because naming a
                `botocore` type here would put a vendor type in a signature,
                which is the exact thing this boundary forbids. The type is
                unavoidable at the vendor edge; what matters is that it never
                travels upward.
            bucket: The single private bucket holding every workspace's objects.
        """
        self._client = client
        self._bucket = bucket

    @property
    def name(self) -> str:
        """Return the stable identifier for this provider."""
        return "cloudflare-r2"

    def put(
        self,
        workspace_id: uuid.UUID,
        logical_name: str,
        data: bytes,
        content_type: str,
    ) -> StoredObject:
        """Store bytes as one workspace's object."""
        key = build_object_key(workspace_id, logical_name)

        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
        except Exception as error:  # noqa: BLE001 - translated below
            raise self._translate(error) from error

        # The locator is the logical name, not `key`. The constructed key stays
        # inside this layer so nothing above it ever holds an S3-shaped string
        # it would have to parse to use again -- see `StoredObject`.
        return StoredObject(locator=logical_name, size_bytes=len(data), content_type=content_type)

    def get(self, workspace_id: uuid.UUID, logical_name: str) -> bytes:
        """Return one workspace's object as bytes."""
        key = build_object_key(workspace_id, logical_name)

        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            body = response["Body"]
            try:
                return bytes(body.read())
            finally:
                # Streaming bodies hold a connection until closed. Leaking them
                # exhausts the pool under load, which surfaces as unrelated
                # timeouts elsewhere -- the kind of failure that is expensive to
                # trace back here.
                close = getattr(body, "close", None)
                if close is not None:
                    close()
        except Exception as error:  # noqa: BLE001 - translated below
            raise self._translate(error) from error

    def signed_url(
        self,
        workspace_id: uuid.UUID,
        logical_name: str,
        expires_in: timedelta,
    ) -> str:
        """Return a time-limited URL granting direct read access to one object."""
        key = build_object_key(workspace_id, logical_name)

        if not MIN_SIGNED_URL_EXPIRY <= expires_in <= MAX_SIGNED_URL_EXPIRY:
            # A `ValueError`, per the contract. Rejected here rather than passed
            # through, because R2 would accept the request and issue a URL that
            # fails only when somebody tries to use it.
            raise ValueError(
                "Signed URL expiry must be between 1 second and 7 days for this backend."
            )

        try:
            url = self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=int(expires_in.total_seconds()),
            )
        except Exception as error:  # noqa: BLE001 - translated below
            raise self._translate(error) from error

        return str(url)

    def delete(self, workspace_id: uuid.UUID, logical_name: str) -> None:
        """Delete one workspace's object, idempotently."""
        key = build_object_key(workspace_id, logical_name)

        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except Exception as error:  # noqa: BLE001 - translated below
            translated = self._translate(error)
            # Idempotent by contract: a delete of something already gone has
            # achieved what the caller asked for. A refusal is still a refusal.
            if isinstance(translated, ObjectNotFoundError):
                return
            raise translated from error

    @staticmethod
    def _translate(error: Exception) -> Exception:
        """Translate a vendor exception into this codebase's storage errors.

        The one place `botocore`'s error shape is interpreted. Callers never see
        a `ClientError`, which is what lets a future adapter replace this one
        without touching anything above it.

        Read defensively: the code is dug out of the response dict rather than
        matched on an exception class, so an SDK reorganising its exception
        hierarchy does not silently turn a 404 into an outage.
        """
        response: Mapping[str, Any] | None = getattr(error, "response", None)
        code = ""
        if isinstance(response, dict):
            error_detail = response.get("Error")
            if isinstance(error_detail, dict):
                code = str(error_detail.get("Code", ""))
            if not code:
                metadata = response.get("ResponseMetadata")
                if isinstance(metadata, dict):
                    code = str(metadata.get("HTTPStatusCode", ""))

        if code in _NOT_FOUND_CODES:
            return ObjectNotFoundError()
        if code in _ACCESS_DENIED_CODES:
            return StorageAccessDeniedError()

        # Anything unrecognised is reported as an outage rather than guessed at.
        # The alternative -- mapping unknown codes onto the nearest-looking
        # error -- produces a caller that handles a case it does not actually
        # understand (CLAUDE.md §24).
        return StorageUnavailableError()
