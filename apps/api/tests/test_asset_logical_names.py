"""Deriving a storage-safe, unique logical name from a user's filename.

**The collision case is the point of this module**, not the sanitising. `put`
overwrites silently and there is no listing operation to check against first, so
two uploads of `photo.png` into one workspace would destroy the first file with
nothing anywhere reporting it. These tests assert that cannot happen, and they
assert it directly rather than inferring it from the presence of a UUID.

Offline and dependency-free: pure functions, no database, no storage, no HTTP.
"""

from __future__ import annotations

import uuid

import pytest

from app.storage.keys import build_object_key
from app.storage.logical_names import (
    MAX_EXTENSION_LENGTH,
    derive_logical_name,
    extension_of,
)


class TestUniqueness:
    """The property that makes silent overwrite impossible."""

    def test_two_uploads_of_the_same_filename_get_different_names(self) -> None:
        """The proof [[STEP-28]] requires, asserted rather than assumed.

        Two assets, same filename, same workspace. If these collided, the second
        upload would replace the first's bytes while both rows still pointed at
        the surviving object.
        """
        first = derive_logical_name(uuid.uuid4(), "photo.png")
        second = derive_logical_name(uuid.uuid4(), "photo.png")

        assert first != second

    def test_the_name_is_derived_from_the_asset_id_alone(self) -> None:
        """Uniqueness must not depend on anything the user controls.

        The same asset id with wildly different filenames produces names that
        differ only in their cosmetic extension -- so the *identity* of the
        object comes entirely from the database, never from client input.
        """
        asset_id = uuid.uuid4()

        assert derive_logical_name(asset_id, "a.png").startswith(str(asset_id))
        assert derive_logical_name(asset_id, "totally-different.png").startswith(str(asset_id))

    def test_the_same_asset_always_maps_to_the_same_object(self) -> None:
        """Deterministic, so a retry addresses the object it created before."""
        asset_id = uuid.uuid4()

        assert derive_logical_name(asset_id, "photo.png") == derive_logical_name(
            asset_id, "photo.png"
        )


class TestTheResultIsAlwaysStorageSafe:
    """Whatever goes in, what comes out satisfies the key boundary."""

    @pytest.mark.parametrize(
        "filename",
        [
            pytest.param("photo.png", id="ordinary"),
            pytest.param("my holiday photo.png", id="spaces"),
            pytest.param("résumé.pdf", id="accents"),
            pytest.param("写真.png", id="non-latin"),
            pytest.param("../../../etc/passwd", id="traversal"),
            pytest.param("photo.png\x00.exe", id="null-byte"),
            pytest.param("%2e%2e%2fescape.png", id="percent-encoded"),
            pytest.param("archive.tar.gz", id="multiple-dots"),
            pytest.param(".hidden", id="leading-dot-only"),
            pytest.param("no-extension", id="no-extension"),
            pytest.param("", id="empty"),
            pytest.param(None, id="absent"),
            pytest.param("x." + "a" * 400, id="absurd-extension"),
            pytest.param("photo.PNG", id="uppercase-extension"),
        ],
    )
    def test_every_filename_produces_a_constructable_key(self, filename: str | None) -> None:
        """`build_object_key` accepts the result for every input, hostile included.

        Asserted against the real key constructor rather than against a regex
        copied from it. A regex here would pass while the boundary rejected the
        value, which is the only thing that actually matters.
        """
        workspace_id = uuid.uuid4()

        logical_name = derive_logical_name(uuid.uuid4(), filename)

        # Raises InvalidLogicalNameError if the derived name is not safe.
        key = build_object_key(workspace_id, logical_name)

        assert key.startswith(f"ws/{workspace_id}/")

    def test_a_traversal_filename_contributes_nothing_at_all(self) -> None:
        """A hostile filename is dropped, never repaired into something plausible."""
        asset_id = uuid.uuid4()

        assert derive_logical_name(asset_id, "../../etc/passwd") == str(asset_id)


class TestExtensionHandling:
    """The cosmetic half: preserved when safe, dropped otherwise."""

    @pytest.mark.parametrize(
        ("filename", "expected"),
        [
            pytest.param("photo.png", "png", id="simple"),
            pytest.param("photo.PNG", "png", id="lowercased"),
            pytest.param("archive.tar.gz", "gz", id="last-segment-only"),
            pytest.param("video.mp4", "mp4", id="alphanumeric"),
            pytest.param("noext", None, id="no-dot"),
            pytest.param("trailing.", None, id="trailing-dot"),
            pytest.param(".hidden", "hidden", id="dotfile-reads-as-extension"),
            pytest.param("photo.p ng", None, id="space-in-extension"),
            pytest.param("photo.p-ng", None, id="hyphen-in-extension"),
            pytest.param("photo." + "a" * (MAX_EXTENSION_LENGTH + 1), None, id="too-long"),
            pytest.param(None, None, id="absent"),
            pytest.param("", None, id="empty"),
        ],
    )
    def test_extension_extraction(self, filename: str | None, expected: str | None) -> None:
        assert extension_of(filename) == expected

    def test_a_safe_extension_is_kept_on_the_derived_name(self) -> None:
        """An operator should be able to tell a PNG from a PDF in a console."""
        asset_id = uuid.uuid4()

        assert derive_logical_name(asset_id, "cover.png") == f"{asset_id}.png"

    def test_extension_extraction_never_raises(self) -> None:
        """Total by design: a bad extension is not a reason to refuse an upload.

        Rejecting *content* is a separate concern, handled against the declared
        type and the bytes themselves. This function must not become a second,
        weaker gate that refuses files for having an unusual name.
        """
        for hostile in ("../..", "\x00", "%2f", "a" * 5000, "..", "."):
            assert extension_of(hostile) is None
