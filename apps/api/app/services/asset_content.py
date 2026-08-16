"""What an uploaded file is allowed to be, and whether it really is that.

Upload endpoints are a classic injection surface, so validation *is* the step
rather than a detail of it ([[STEP-28 Asset Upload and Download]] Risks). This
module owns every rule about the bytes themselves; it knows nothing about HTTP,
storage or the database, so the rules can be tested without any of them
(CLAUDE.md §12).

## Four independent checks, cheapest first

1. **Size**, against a per-asset ceiling.
2. **Declared MIME type**, against an allowlist derived from `AssetKind`.
3. **Extension**, against the same allowlist entry.
4. **Content**, by reading the file's magic bytes and requiring them to agree
   with what was declared.

Ordered so the cheapest rejection happens first, but **each is independent**:
none is load-bearing alone, and removing any one of them widens what gets
stored. In particular the fourth is what makes the third meaningful — an
extension and a declared type are both client-supplied strings, and a `.png`
whose content is a Windows executable satisfies the first three checks
perfectly.

## Why the signature table is small and explicit

No `libmagic`, no `python-magic`, no third-party sniffer. A dependency whose
whole job is reading the first few bytes of a file is a dependency for a one-off
need (CLAUDE.md §28), and the general-purpose ones detect hundreds of formats
this product does not accept — breadth is a liability here, not a feature. Four
kinds of asset with a handful of formats each is a table a reader can verify
against a specification in a minute.

## What this deliberately does not do

**No repair, no transcoding, no normalisation.** A file that fails any check is
refused, never fixed. [[STEP-32 Media Processing Pipeline]] owns transformation.

**No quota accounting.** The ceiling here is per asset. Per-workspace totals are
[[STEP-33 Storage Quotas and Lifecycle]].
"""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.project import AssetKind

#: The largest single asset accepted, in bytes.
#:
#: **100 MB, set by the project owner on 2026-08-16** ([[STEP-28 Asset Upload and
#: Download#Decisions]] D2), and worded there as the *initial* limit.
#:
#: This ceiling and the absence of multipart upload are one decision seen twice.
#: `StorageProvider.put` takes `data: bytes`, so an accepted upload is held in
#: memory in full — raising this number without changing the transport raises the
#: memory a single request can consume, which is a availability decision rather
#: than a configuration tweak. A genuine need for larger media is a signal to
#: revisit the transport, not to edit this constant.
#:
#: Named rather than written at the check site because
#: [[STEP-33 Storage Quotas and Lifecycle]] will need to reference it when it
#: sets per-workspace totals.
MAX_UPLOAD_BYTES = 100 * 1024 * 1024

#: How many leading bytes are enough to identify every accepted format.
#:
#: 12 covers the longest signature in the table below (WebP, whose marker sits at
#: offset 8). Reading a fixed small prefix rather than the whole file keeps
#: sniffing constant-cost regardless of upload size.
SNIFF_BYTES = 12


class AssetContentError(Exception):
    """An uploaded file was refused on its own merits.

    Carries `public_message` and `status_code` so `app.core.errors` can answer
    every subclass through one handler. The alternative — a handler per subclass
    returning near-identical bodies — is four places for one contract to drift.

    **No message in this hierarchy echoes the filename.** A filename is
    caller-controlled input, and reflecting it into an error that reaches a log
    or a response body is how one injection becomes two (CLAUDE.md §24; the same
    rule `InvalidLogicalNameError` already follows).
    """

    #: Safe to surface to an API caller. Overridden by subclasses.
    public_message = "The uploaded file was refused."

    #: The HTTP status this refusal deserves. Overridden by subclasses.
    status_code = 400

    def __init__(self, message: str | None = None) -> None:
        """Initialise the error, defaulting to the class's public message."""
        super().__init__(message or self.public_message)


class AssetTooLargeError(AssetContentError):
    """The upload exceeded the per-asset ceiling."""

    public_message = (
        f"The file is larger than the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit for one asset."
    )
    status_code = 413


class UnsupportedContentTypeError(AssetContentError):
    """The declared MIME type is not accepted for this kind of asset."""

    public_message = "That file type is not supported for this kind of asset."
    status_code = 415


class ExtensionMismatchError(AssetContentError):
    """The filename's extension does not match the declared type."""

    public_message = "The file's extension does not match its declared type."
    status_code = 415


class ContentMismatchError(AssetContentError):
    """The file's actual content does not match what was declared.

    The check that makes the other three meaningful: a declared type and an
    extension are strings a client chooses, while the leading bytes are the file.
    """

    public_message = "The file's contents do not match its declared type."
    status_code = 415


class EmptyUploadError(AssetContentError):
    """The upload carried no bytes.

    Refused rather than stored. A zero-byte object is indistinguishable from a
    failed upload that got as far as creating one, and storing it would make the
    orphan reasoning in Task 5 unfalsifiable.
    """

    public_message = "The file is empty."
    status_code = 400


@dataclass(frozen=True)
class AllowedType:
    """One accepted format: what it is called, and how it is recognised."""

    #: The MIME type a client must declare for this format.
    mime: str

    #: The kind of asset this format may be attached as.
    kind: AssetKind

    #: Permitted filename extensions, lowercased and without the dot.
    extensions: tuple[str, ...]

    #: Byte prefixes identifying the format, as `(offset, marker)` pairs. A
    #: format matches when **every** pair matches. Several alternatives are
    #: expressed as several `AllowedType` entries sharing a MIME type rather than
    #: as an "any of" rule, so each row stays readable.
    signatures: tuple[tuple[int, bytes], ...]


#: Every format ProjectOne accepts today, grouped by the `AssetKind` it belongs
#: to. Deliberately conservative: a format absent here is refused, which is the
#: correct default for a boundary that accepts arbitrary user files.
#:
#: Two MIME types appear twice (`image/jpeg`, `video/mp4`) because one format has
#: more than one legitimate byte signature. Matching is "any entry with this MIME
#: type", so both spellings are accepted without an "any of" branch in the
#: matching code.
ALLOWED_TYPES: tuple[AllowedType, ...] = (
    # --- images ---
    AllowedType(
        mime="image/png",
        kind=AssetKind.IMAGE,
        extensions=("png",),
        signatures=((0, b"\x89PNG\r\n\x1a\n"),),
    ),
    AllowedType(
        mime="image/jpeg",
        kind=AssetKind.IMAGE,
        extensions=("jpg", "jpeg"),
        signatures=((0, b"\xff\xd8\xff"),),
    ),
    AllowedType(
        mime="image/gif",
        kind=AssetKind.IMAGE,
        extensions=("gif",),
        signatures=((0, b"GIF89a"),),
    ),
    AllowedType(
        mime="image/gif",
        kind=AssetKind.IMAGE,
        extensions=("gif",),
        signatures=((0, b"GIF87a"),),
    ),
    AllowedType(
        mime="image/webp",
        kind=AssetKind.IMAGE,
        extensions=("webp",),
        # RIFF container: "RIFF" then four length bytes then "WEBP".
        signatures=((0, b"RIFF"), (8, b"WEBP")),
    ),
    # --- documents ---
    AllowedType(
        mime="application/pdf",
        kind=AssetKind.DOCUMENT,
        extensions=("pdf",),
        signatures=((0, b"%PDF-"),),
    ),
    # --- video ---
    AllowedType(
        mime="video/mp4",
        kind=AssetKind.VIDEO,
        extensions=("mp4", "m4v"),
        # ISO base media: a 4-byte box length, then the `ftyp` box type.
        signatures=((4, b"ftyp"),),
    ),
    AllowedType(
        mime="video/webm",
        kind=AssetKind.VIDEO,
        extensions=("webm",),
        signatures=((0, b"\x1a\x45\xdf\xa3"),),
    ),
    # --- audio ---
    AllowedType(
        mime="audio/mpeg",
        kind=AssetKind.AUDIO,
        extensions=("mp3",),
        # ID3-tagged MP3. The bare-frame form (`\xff\xfb`) is the second entry.
        signatures=((0, b"ID3"),),
    ),
    AllowedType(
        mime="audio/mpeg",
        kind=AssetKind.AUDIO,
        extensions=("mp3",),
        signatures=((0, b"\xff\xfb"),),
    ),
    AllowedType(
        mime="audio/wav",
        kind=AssetKind.AUDIO,
        extensions=("wav",),
        signatures=((0, b"RIFF"), (8, b"WAVE")),
    ),
)


def _matches(head: bytes, allowed: AllowedType) -> bool:
    """Return whether `head` carries every signature `allowed` requires."""
    return all(
        head[offset : offset + len(marker)] == marker for offset, marker in allowed.signatures
    )


def validate_upload(
    kind: AssetKind,
    declared_content_type: str | None,
    extension: str | None,
    head: bytes,
    size_bytes: int,
) -> AllowedType:
    """Validate one upload and return the format it was accepted as.

    Returns the matched `AllowedType` rather than None so the caller stores the
    *canonical* MIME type rather than the client's spelling — a client sending
    `image/png; charset=utf-8` or an unexpected case should not decide what is
    recorded against the object.

    Args:
        kind: The asset kind the client is attaching this as.
        declared_content_type: The MIME type the client declared. A parameterised
            value (`type/subtype; charset=...`) is reduced to its type/subtype.
        extension: The lowercased extension, or None when the filename had none.
        head: The file's first bytes, at least `SNIFF_BYTES` where available.
        size_bytes: The upload's full length.

    Returns:
        The `AllowedType` the upload satisfied.

    Raises:
        EmptyUploadError: the upload carried no bytes.
        AssetTooLargeError: the upload exceeds `MAX_UPLOAD_BYTES`.
        UnsupportedContentTypeError: the declared type is not accepted for
            `kind`.
        ExtensionMismatchError: the extension is not one this format uses.
        ContentMismatchError: the bytes do not match the declared format.
    """
    # 1. Size. First because it is the only check that can be true of a file too
    #    large to have been read, and the caller enforces it while streaming.
    if size_bytes <= 0:
        raise EmptyUploadError()

    if size_bytes > MAX_UPLOAD_BYTES:
        raise AssetTooLargeError()

    # 2. Declared type, narrowed to the entries valid for this kind. Checking
    #    against `kind` here is what stops an executable being attached as an
    #    `image` simply by declaring `application/pdf` — the type must be
    #    accepted *and* belong to the kind the row will claim.
    normalised = (declared_content_type or "").split(";")[0].strip().lower()
    candidates = tuple(
        allowed for allowed in ALLOWED_TYPES if allowed.mime == normalised and allowed.kind == kind
    )

    if not candidates:
        raise UnsupportedContentTypeError()

    # 3. Extension, against the union across candidates sharing this MIME type.
    #    Absent is permitted: a file with no extension is ordinary, and the
    #    content check below is the one that actually constrains what is stored.
    if extension is not None:
        permitted = {value for allowed in candidates for value in allowed.extensions}

        if extension not in permitted:
            raise ExtensionMismatchError()

    # 4. Content. The check the other three depend on for their meaning.
    for allowed in candidates:
        if _matches(head, allowed):
            return allowed

    raise ContentMismatchError()
