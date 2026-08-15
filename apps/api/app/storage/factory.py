"""Assembles the configured storage provider.

The one place credentials are unwrapped and an S3 client is constructed. Keeping
that here rather than at each construction site means `.get_secret_value()` is
called in exactly one function, which is the property worth having when the value
being unwrapped is a credential (CLAUDE.md §16).

`boto3` is imported **inside** the factory function rather than at module scope.
That is deliberate and load-bearing in two ways:

- It keeps the import cost off every process that never touches storage.
- It keeps this module importable in an environment without `boto3` installed,
  so the architectural boundary test can import and inspect the storage package
  without the SDK being present.

The vendor type never escapes: this function returns `StorageProvider`, and the
client it built is held privately by the adapter
([[ADR-004 Object Storage Provider and Tenant-Safe Key Construction]] §3).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.storage.provider import StorageProvider
from app.storage.providers.r2 import R2_REGION, R2StorageProvider

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.core.config import Settings


class StorageNotConfiguredError(RuntimeError):
    """Storage was requested but the deployment has no storage configuration.

    A `RuntimeError` rather than a storage error: this is a deployment fault, not
    a failed storage operation, and conflating the two would let a caller
    `except StorageError` its way past a misconfiguration.
    """


def build_storage_provider(settings: Settings) -> StorageProvider:
    """Return the configured storage provider.

    Args:
        settings: The process configuration.

    Returns:
        A `StorageProvider` — the vendor-neutral type. That the concrete class is
        `R2StorageProvider` is an implementation detail of this function, and no
        caller may depend on it.

    Raises:
        StorageNotConfiguredError: if any required storage variable is missing.
            Raised at the point of use, with a message naming what is absent,
            rather than at startup where it would break deployments that never
            touch storage.
    """
    if not settings.storage_is_configured:
        raise StorageNotConfiguredError(
            "Object storage is not configured. Set PROJECTONE_R2_ACCOUNT_ID, "
            "PROJECTONE_R2_BUCKET, PROJECTONE_R2_ACCESS_KEY_ID and "
            "PROJECTONE_R2_SECRET_ACCESS_KEY. See apps/api/.env.example."
        )

    import boto3  # noqa: PLC0415 - deferred on purpose; see module docstring

    # `storage_is_configured` has established all four are present; the local
    # names keep mypy aware of that without scattering asserts.
    endpoint_url = settings.r2_endpoint_url
    bucket = settings.r2_bucket
    access_key_id = settings.r2_access_key_id
    secret_access_key = settings.r2_secret_access_key
    assert endpoint_url is not None  # noqa: S101 - narrowing after the check above
    assert bucket is not None  # noqa: S101
    assert access_key_id is not None  # noqa: S101
    assert secret_access_key is not None  # noqa: S101

    client = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        # Passed explicitly rather than left to the environment: an inherited
        # AWS_DEFAULT_REGION would otherwise decide it, which is a surprising
        # dependency on ambient state for a value R2 fixes at `auto`.
        region_name=R2_REGION,
        aws_access_key_id=access_key_id.get_secret_value(),
        aws_secret_access_key=secret_access_key.get_secret_value(),
    )

    return R2StorageProvider(client=client, bucket=bucket)
