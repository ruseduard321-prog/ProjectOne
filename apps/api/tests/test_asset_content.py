"""What an uploaded file is allowed to be, checked four independent ways.

The rules live in a service with no HTTP, no storage and no database, so they are
tested the same way — these cases construct bytes directly and assert against the
validator. The route-level proofs that the same rules reach a client as the right
status live in `test_asset_upload_api.py`.

**The case that matters most is `test_an_extension_that_lies_about_its_content_is_refused`.**
An extension and a declared MIME type are both strings a client chooses; the
leading bytes are the file. Without the content check the other three are a
politeness agreement with the uploader.
"""

from __future__ import annotations

import pytest

from app.schemas.project import AssetKind
from app.services.asset_content import (
    ALLOWED_TYPES,
    MAX_UPLOAD_BYTES,
    SNIFF_BYTES,
    AssetTooLargeError,
    ContentMismatchError,
    EmptyUploadError,
    ExtensionMismatchError,
    UnsupportedContentTypeError,
    validate_upload,
)

#: Real leading bytes for each format the product accepts. Written out rather
#: than generated from `ALLOWED_TYPES`, deliberately: generating them from the
#: table under test would make every assertion circular -- the table would agree
#: with itself whatever it contained.
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 8
GIF = b"GIF89a" + b"\x00" * 8
WEBP = b"RIFF\x24\x00\x00\x00WEBP" + b"\x00" * 4
PDF = b"%PDF-1.7\n" + b"\x00" * 8
MP4 = b"\x00\x00\x00\x20ftypisom" + b"\x00" * 4
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 8
MP3 = b"ID3\x04\x00\x00" + b"\x00" * 8
WAV = b"RIFF\x24\x00\x00\x00WAVE" + b"\x00" * 4

#: A Windows executable. The canonical "extension lies" payload.
EXE = b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 8


def accept(
    kind: AssetKind,
    content_type: str,
    extension: str | None,
    head: bytes,
    size_bytes: int = 1024,
) -> str:
    """Validate an upload and return the canonical MIME type it matched."""
    return validate_upload(
        kind=kind,
        declared_content_type=content_type,
        extension=extension,
        head=head[:SNIFF_BYTES],
        size_bytes=size_bytes,
    ).mime


class TestAcceptedFormats:
    """Every format in the table is genuinely accepted end to end."""

    @pytest.mark.parametrize(
        ("kind", "content_type", "extension", "head"),
        [
            pytest.param(AssetKind.IMAGE, "image/png", "png", PNG, id="png"),
            pytest.param(AssetKind.IMAGE, "image/jpeg", "jpg", JPEG, id="jpeg-jpg"),
            pytest.param(AssetKind.IMAGE, "image/jpeg", "jpeg", JPEG, id="jpeg-jpeg"),
            pytest.param(AssetKind.IMAGE, "image/gif", "gif", GIF, id="gif"),
            pytest.param(AssetKind.IMAGE, "image/webp", "webp", WEBP, id="webp"),
            pytest.param(AssetKind.DOCUMENT, "application/pdf", "pdf", PDF, id="pdf"),
            pytest.param(AssetKind.VIDEO, "video/mp4", "mp4", MP4, id="mp4"),
            pytest.param(AssetKind.VIDEO, "video/webm", "webm", WEBM, id="webm"),
            pytest.param(AssetKind.AUDIO, "audio/mpeg", "mp3", MP3, id="mp3"),
            pytest.param(AssetKind.AUDIO, "audio/wav", "wav", WAV, id="wav"),
        ],
    )
    def test_a_valid_upload_is_accepted(
        self,
        kind: AssetKind,
        content_type: str,
        extension: str,
        head: bytes,
    ) -> None:
        assert accept(kind, content_type, extension, head) == content_type

    def test_a_file_with_no_extension_is_accepted(self) -> None:
        """An extension is cosmetic; the content check is what constrains."""
        assert accept(AssetKind.IMAGE, "image/png", None, PNG) == "image/png"

    def test_a_parameterised_content_type_is_normalised(self) -> None:
        """`image/png; charset=binary` is the same declaration as `image/png`."""
        assert accept(AssetKind.IMAGE, "image/png; charset=binary", "png", PNG) == "image/png"

    def test_the_canonical_type_is_returned_not_the_clients_spelling(self) -> None:
        """What is recorded against the object must not be client-chosen casing."""
        assert accept(AssetKind.IMAGE, "IMAGE/PNG", "png", PNG) == "image/png"

    def test_every_declared_type_in_the_table_belongs_to_exactly_one_kind(self) -> None:
        """A MIME type spanning two kinds would make the kind check meaningless.

        `image/jpeg` and `video/mp4` legitimately appear twice, for two byte
        signatures each -- but always under the same `AssetKind`.
        """
        kinds_by_mime: dict[str, set[AssetKind]] = {}

        for allowed in ALLOWED_TYPES:
            kinds_by_mime.setdefault(allowed.mime, set()).add(allowed.kind)

        assert all(len(kinds) == 1 for kinds in kinds_by_mime.values())


class TestContentIsCheckedAgainstTheBytes:
    """The check that gives the other three their meaning."""

    def test_an_extension_that_lies_about_its_content_is_refused(self) -> None:
        """A `.png` whose content is a Windows executable.

        The required proof from [[STEP-28#Required Tests and Proofs]]. Every
        client-supplied claim here is consistent and correct -- kind `image`,
        type `image/png`, extension `png` -- and the file is still refused,
        because the bytes are an executable.
        """
        with pytest.raises(ContentMismatchError):
            accept(AssetKind.IMAGE, "image/png", "png", EXE)

    def test_a_pdf_declared_as_an_image_is_refused(self) -> None:
        """Real, harmless content, but not what was declared."""
        with pytest.raises(ContentMismatchError):
            accept(AssetKind.IMAGE, "image/png", "png", PDF)

    def test_truncated_content_is_refused_rather_than_guessed(self) -> None:
        """Too few bytes to identify is a refusal, not a benefit of the doubt."""
        with pytest.raises(ContentMismatchError):
            accept(AssetKind.IMAGE, "image/png", "png", b"\x89PN")

    def test_a_webp_header_is_not_satisfied_by_riff_alone(self) -> None:
        """Both parts of a two-part signature must match.

        WAV and WebP share the `RIFF` prefix and differ at offset 8. A matcher
        checking only the first marker would accept either as the other.
        """
        with pytest.raises(ContentMismatchError):
            accept(AssetKind.IMAGE, "image/webp", "webp", WAV)


class TestDeclaredTypeAndKindMustAgree:
    """A type is only acceptable for the kind of asset that claims it."""

    def test_an_unknown_type_is_refused(self) -> None:
        with pytest.raises(UnsupportedContentTypeError):
            accept(AssetKind.DOCUMENT, "application/x-msdownload", "exe", EXE)

    def test_a_missing_type_is_refused(self) -> None:
        """No declaration is not an invitation to sniff and accept."""
        with pytest.raises(UnsupportedContentTypeError):
            accept(AssetKind.IMAGE, "", "png", PNG)

    def test_a_valid_type_under_the_wrong_kind_is_refused(self) -> None:
        """A real PDF, attached as an `image`.

        Without the kind check this would be accepted: the type is supported and
        the bytes match it. What makes it wrong is that the row would claim to be
        an image, and every consumer of `kind` would believe it.
        """
        with pytest.raises(UnsupportedContentTypeError):
            accept(AssetKind.IMAGE, "application/pdf", "pdf", PDF)


class TestExtensionMustMatchTheDeclaredType:
    """A cheap check, and an independent one."""

    def test_a_mismatched_extension_is_refused(self) -> None:
        with pytest.raises(ExtensionMismatchError):
            accept(AssetKind.IMAGE, "image/png", "jpg", PNG)

    def test_an_alternative_spelling_is_accepted(self) -> None:
        """`jpg` and `jpeg` are the same format, and both are permitted."""
        assert accept(AssetKind.IMAGE, "image/jpeg", "jpeg", JPEG) == "image/jpeg"


class TestSize:
    """The ceiling, and the two ways past it that must not exist."""

    def test_an_upload_above_the_ceiling_is_refused(self) -> None:
        with pytest.raises(AssetTooLargeError):
            accept(AssetKind.IMAGE, "image/png", "png", PNG, size_bytes=MAX_UPLOAD_BYTES + 1)

    def test_an_upload_exactly_at_the_ceiling_is_accepted(self) -> None:
        """The boundary is inclusive; an off-by-one here refuses a legal file."""
        assert accept(AssetKind.IMAGE, "image/png", "png", PNG, size_bytes=MAX_UPLOAD_BYTES)

    def test_an_empty_upload_is_refused(self) -> None:
        """A zero-byte object is indistinguishable from a failed upload."""
        with pytest.raises(EmptyUploadError):
            accept(AssetKind.IMAGE, "image/png", "png", b"", size_bytes=0)

    def test_the_ceiling_is_the_owners_decision(self) -> None:
        """100 MB, set on 2026-08-16 (D2).

        Pinned so that changing it is a deliberate act with a test to update,
        rather than a number someone edits while tuning something else. The
        constant and the transport are one decision: `put` takes `bytes`, so
        raising this raises what a single request can hold in memory.
        """
        assert MAX_UPLOAD_BYTES == 100 * 1024 * 1024


class TestChecksAreIndependent:
    """Each rule refuses on its own, without relying on a later one."""

    def test_size_is_checked_before_anything_else(self) -> None:
        """An oversized file is refused even when its content is nonsense.

        Ordering matters here beyond neatness: the size check is the one that
        protects the server, and it must not be reachable only after work that
        depends on reading the file.
        """
        with pytest.raises(AssetTooLargeError):
            accept(AssetKind.IMAGE, "not/a-type", "zzz", EXE, size_bytes=MAX_UPLOAD_BYTES + 1)

    def test_type_is_checked_before_content(self) -> None:
        """An unsupported type is refused as such, not as a content mismatch.

        The distinction reaches the client as a different message, and telling
        someone their PNG is corrupt when the real answer is "we do not accept
        that format" sends them to fix the wrong thing.
        """
        with pytest.raises(UnsupportedContentTypeError):
            accept(AssetKind.IMAGE, "image/tiff", "tiff", EXE)
