"""Deriving a storage-safe logical name from a user's filename.

`app.storage.keys` accepts `[A-Za-z0-9._-]{1,200}` and nothing else. A filename
a user actually uploads frequently fails that — spaces, accents, non-Latin
scripts and several dots are all ordinary — so something has to stand between
the two, and this module is it ([[STEP-28 Asset Upload and Download]] Task 2).

## Uniqueness is the point, not tidiness

Sanitising is the obvious half and the less important one. `StorageProvider.put`
**overwrites an existing key silently**, and the key is `ws/<workspace>/<name>`,
so two uploads of `photo.png` into one workspace would leave the first file's
bytes replaced by the second's — with both asset rows still pointing at the
surviving object, and no error anywhere.

There is deliberately no listing operation to check against first (ADR-004), so
a pre-write existence check is not available even in principle. Uniqueness has to
be *constructed* rather than verified, which is why the name is derived from the
asset row's `id`: a UUID minted by the database for this asset and no other.

The original filename is kept in `assets.name`, where a human-readable value
belongs. Storage sees a name it can hold; the user sees the name they chose.

## Why the extension survives at all

Nothing functional depends on it — the content type is stored with the object and
carried on the asset row. It is preserved because an operator looking at a bucket
should be able to tell a PNG from a PDF without opening it, and because a signed
URL ending in `.png` behaves better in a browser than one ending in a bare UUID.

It is *cosmetic*, and it is treated as such: anything outside a conservative
allowlist is dropped rather than repaired. Transliterating `résumé.pdf` into
`resume.pdf` would be guessing at intent, and the guess is not needed — the real
name is already safe in the database.
"""

from __future__ import annotations

import re
import uuid

#: The longest extension kept. Comfortably above real ones (`jpeg`, `webp`,
#: `mp4`) and short enough that a pathological "extension" is dropped instead of
#: padding the key.
MAX_EXTENSION_LENGTH = 10

#: What an extension may contain once lowercased: ASCII letters and digits.
#:
#: Narrower than the key module's allowlist on purpose. That one has to admit
#: dot, hyphen and underscore because it validates a whole name; an *extension*
#: containing any of them is not an extension this code should be preserving, so
#: it is dropped and the object keeps a bare-UUID name.
_EXTENSION_PATTERN = re.compile(r"\A[a-z0-9]+\Z")


def extension_of(filename: str | None) -> str | None:
    """Return the lowercased extension of `filename`, or None if unusable.

    Deliberately total: every input returns a value or None, and nothing raises.
    A filename with no extension, a hostile one, or none at all are the same
    outcome here — an object named by its UUID alone — because the extension is
    cosmetic and a *missing* one is not a reason to refuse an upload.

    Rejection of the file's actual content type is a separate concern that
    happens elsewhere, against the declared type and the bytes themselves
    (`app.services.asset_content`). This function is not a security control and
    must not be read as one.

    Args:
        filename: The client-supplied filename, which may be absent.

    Returns:
        The extension without its dot, lowercased, or None.
    """
    if not filename:
        return None

    # `rpartition` rather than `split(".")`: only the final dot separates an
    # extension, and `archive.tar.gz` keeps `gz` rather than becoming `tar.gz`,
    # which is not in the allowlist anyway.
    _, dot, candidate = filename.rpartition(".")

    if not dot or not candidate:
        return None

    lowered = candidate.lower()

    if len(lowered) > MAX_EXTENSION_LENGTH or not _EXTENSION_PATTERN.match(lowered):
        return None

    return lowered


def derive_logical_name(asset_id: uuid.UUID, filename: str | None = None) -> str:
    """Return the storage logical name for one asset.

    **Unique by construction.** The name is built from `asset_id`, so two uploads
    of identically-named files produce two distinct objects and neither can
    overwrite the other. Nothing about the caller's filename influences
    uniqueness, which is what makes that guarantee independent of user input.

    Always satisfies `app.storage.keys`: a canonical UUID string contains only
    hex digits and hyphens, and any extension appended has already been reduced
    to lowercase alphanumerics. `put` validates again regardless — this function
    being correct is not a reason for the boundary to trust it.

    Args:
        asset_id: The asset row's primary key. The source of uniqueness.
        filename: The client-supplied filename, used only for its extension.

    Returns:
        `<asset-uuid>` or `<asset-uuid>.<ext>`, at most 47 characters.
    """
    extension = extension_of(filename)

    if extension is None:
        return str(asset_id)

    return f"{asset_id}.{extension}"
