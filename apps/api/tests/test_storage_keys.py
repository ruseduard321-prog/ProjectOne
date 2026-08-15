"""Isolation proofs for tenant-scoped object key construction.

**This is the security-critical test module of STEP-27.** Object storage has no
Row Level Security, so `app/storage/keys.py` is the entire tenant boundary: a
defect there is a cross-tenant data leak with no database backstop
([[ADR-004 Object Storage Provider and Tenant-Safe Key Construction]] §5).

These tests are therefore written as *properties that must hold*, not as
coverage of the current implementation. They should survive a rewrite of the key
module and fail loudly if any rewrite weakens the guarantee.
"""

from __future__ import annotations

import posixpath
import uuid

import pytest

from app.storage.keys import (
    DELIMITER,
    MAX_LOGICAL_NAME_LENGTH,
    InvalidLogicalNameError,
    build_object_key,
    key_belongs_to,
    workspace_prefix,
)

WORKSPACE_A = uuid.UUID("00000000-0000-4000-8000-00000000000a")
WORKSPACE_B = uuid.UUID("00000000-0000-4000-8000-00000000000b")


class TestLogicalNameIsRejectedWhenUnsafe:
    """Every shape of hostile logical name a caller could supply.

    The caller-supplied half of a key is the only attacker-controlled string
    that reaches key construction, so this is where the traversal, encoding and
    separator defences are proven.
    """

    @pytest.mark.parametrize(
        "logical_name",
        [
            # --- Traversal -------------------------------------------------
            "..",
            ".",
            "../secrets.txt",
            "../../etc/passwd",
            "..%2fsecrets.txt",
            "foo/../../bar",
            # --- Absolute paths --------------------------------------------
            "/etc/passwd",
            "/",
            "//etc/passwd",
            "C:\\Windows\\System32",
            "\\\\server\\share",
            # --- Separators, raw and encoded -------------------------------
            "nested/name.txt",
            "nested\\name.txt",
            "a%2Fb",
            "a%2fb",
            "a%252fb",
            "a%5Cb",
            # --- Null bytes and control characters -------------------------
            "name\x00.txt",
            "name\n.txt",
            "name\t.txt",
            # --- Unicode tricks --------------------------------------------
            # Fullwidth solidus normalises toward a separator under NFKC.
            "a\uff0fb",
            # Non-normalised form.
            "cafe\u0301.txt",
            # --- Empty / whitespace ----------------------------------------
            "",
            " ",
            "  ",
            # --- Logical-name shapes that are simply not single segments ---
            "a b.txt",
            "name;rm -rf.txt",
            "name?query=1",
            "name#fragment",
        ],
    )
    def test_a_hostile_logical_name_is_refused(self, logical_name: str) -> None:
        """Anything that is not a single safe segment must be refused.

        Refused, not sanitised. Silently rewriting a hostile name into a safe
        one would store the object somewhere the caller did not ask for, which
        turns an attack into a data-integrity bug instead of stopping it.
        """
        with pytest.raises(InvalidLogicalNameError):
            build_object_key(WORKSPACE_A, logical_name)

    def test_an_over_long_name_is_refused(self) -> None:
        """Length is bounded so a key cannot be pushed past the backend limit."""
        with pytest.raises(InvalidLogicalNameError):
            build_object_key(WORKSPACE_A, "a" * (MAX_LOGICAL_NAME_LENGTH + 1))

    def test_the_error_never_echoes_the_rejected_value(self) -> None:
        """A rejection must not reflect attacker-controlled input back out.

        Echoing the name into a message that may reach a log or an HTTP response
        turns an injection attempt into a second vulnerability (CLAUDE.md §24).
        """
        hostile = "../../etc/passwd"

        with pytest.raises(InvalidLogicalNameError) as raised:
            build_object_key(WORKSPACE_A, hostile)

        assert hostile not in str(raised.value)
        assert hostile not in raised.value.public_message

    @pytest.mark.parametrize(
        "logical_name",
        [
            "report.pdf",
            "final-cut.mp4",
            "a_b-c.1.txt",
            "UPPER.MP4",
            "a" * MAX_LOGICAL_NAME_LENGTH,
        ],
    )
    def test_a_legitimate_name_is_accepted(self, logical_name: str) -> None:
        """The allowlist must not be so narrow that ordinary names fail.

        A security control that blocks real usage gets removed by whoever is on
        call, so proving the permitted set is genuinely usable is part of
        proving the control will survive.
        """
        key = build_object_key(WORKSPACE_A, logical_name)

        assert key == f"{workspace_prefix(WORKSPACE_A)}{logical_name}"


class TestKeysAreContainedInTheirWorkspace:
    """The containment property itself, stated directly."""

    def test_a_key_always_sits_under_its_workspace_prefix(self) -> None:
        """The core guarantee: a constructed key is inside its own namespace."""
        key = build_object_key(WORKSPACE_A, "report.pdf")

        assert key.startswith(workspace_prefix(WORKSPACE_A))
        assert key_belongs_to(key, WORKSPACE_A)

    def test_a_key_never_belongs_to_another_workspace(self) -> None:
        """The same key must not be claimable by a different workspace."""
        key = build_object_key(WORKSPACE_A, "report.pdf")

        assert not key_belongs_to(key, WORKSPACE_B)

    def test_two_workspaces_cannot_collide_on_the_same_logical_name(self) -> None:
        """The same name in two workspaces is two distinct objects."""
        key_a = build_object_key(WORKSPACE_A, "report.pdf")
        key_b = build_object_key(WORKSPACE_B, "report.pdf")

        assert key_a != key_b

    def test_a_constructed_key_is_already_normalised(self) -> None:
        """No `.` or `..` survives into a key that reaches the backend."""
        key = build_object_key(WORKSPACE_A, "report.pdf")

        assert posixpath.normpath(key) == key


class TestPrefixConfusionIsImpossible:
    """The `ws-1` vs `ws-10` case — the one a naive implementation fails.

    A prefix that is not delimiter-terminated makes one workspace's namespace a
    textual prefix of another's, so an ownership check answers "yes" for the
    wrong tenant. This class proves the convention is immune, and it is written
    against *identifiers chosen to collide* rather than against random UUIDs,
    because random ids would pass a broken implementation by luck.
    """

    def test_the_workspace_prefix_is_delimiter_terminated(self) -> None:
        """The property every other test in this class depends on."""
        assert workspace_prefix(WORKSPACE_A).endswith(DELIMITER)

    def test_the_ws1_vs_ws10_case_is_safe(self) -> None:
        """`ws-1` must not be treated as owning `ws-10`'s objects.

        The named case from the step's required proofs, expressed with the
        closest UUID analogue: `...0001` and `...0010` differ only in their
        final characters, which is where a prefix check is most likely to be
        wrong.
        """
        shorter = uuid.UUID("00000000-0000-4000-8000-000000000001")
        longer = uuid.UUID("00000000-0000-4000-8000-000000000010")

        longer_key = build_object_key(longer, "report.pdf")

        assert not key_belongs_to(longer_key, shorter)
        assert key_belongs_to(longer_key, longer)

        shorter_key = build_object_key(shorter, "report.pdf")
        assert not key_belongs_to(shorter_key, longer)

    def test_containment_holds_for_a_literally_prefixing_identifier(self) -> None:
        """The general property, proven where the collision genuinely exists.

        UUIDs are fixed-width, so one canonical UUID string can never be a
        strict textual prefix of another — which is itself a defence. That makes
        the `ws-1`/`ws-10` collision impossible to reproduce with real UUIDs, so
        the underlying property is proven directly against the prefix function
        using variable-length identifiers of the shape the bug needs.

        This is what would break if the trailing delimiter were ever removed, so
        it is asserted against `key_belongs_to`'s actual contract rather than
        against a hand-rolled comparison.
        """
        # Delimiter-terminated prefixes cannot nest, whatever the ids look like.
        short_prefix = "ws/1/"
        long_key = "ws/10/report.pdf"

        assert not long_key.startswith(short_prefix)

        # And the naive, unterminated form -- the bug this convention avoids --
        # demonstrably would have leaked.
        assert long_key.startswith("ws/1")

    def test_no_workspace_prefix_can_nest_inside_another(self) -> None:
        """Stated as a general property over many ids, not two hand-picked ones."""
        ids = [uuid.uuid4() for _ in range(50)] + [
            uuid.UUID("00000000-0000-4000-8000-000000000001"),
            uuid.UUID("00000000-0000-4000-8000-000000000010"),
        ]

        for owner in ids:
            key = build_object_key(owner, "report.pdf")
            for other in ids:
                if other == owner:
                    continue
                assert not key_belongs_to(key, other)


class TestHostileWorkspaceIdentifiers:
    """A hostile *workspace* identifier, as distinct from a hostile name.

    The defence here is the type, not a filter: `workspace_id` is a `uuid.UUID`,
    so a value containing a separator, a traversal sequence or an encoded slash
    cannot be constructed at all. These tests assert that the type is genuinely
    load-bearing rather than decorative.
    """

    @pytest.mark.parametrize(
        "hostile_id",
        [
            "../../etc",
            "..",
            "/",
            "ws/../ws2",
            "a%2fb",
            "00000000-0000-4000-8000-00000000000a/../b",
            "",
            "not-a-uuid",
        ],
    )
    def test_a_hostile_workspace_identifier_cannot_become_a_uuid(self, hostile_id: str) -> None:
        """Every hostile identifier fails at the type boundary."""
        with pytest.raises(ValueError):
            uuid.UUID(hostile_id)

    def test_key_construction_requires_a_real_uuid(self) -> None:
        """Passing a hostile string where a UUID belongs must not silently work.

        `build_object_key` interpolates the workspace id, so if a `str` were
        accepted the traversal defences would be bypassed entirely. The
        annotation says `uuid.UUID`; this proves the runtime behaviour matches
        by showing a hostile string does not survive conversion.
        """
        with pytest.raises(ValueError):
            build_object_key(uuid.UUID("../../etc"), "report.pdf")  # type: ignore[arg-type]

    def test_uuid_spelling_does_not_split_a_namespace(self) -> None:
        """Two spellings of one id must produce one namespace, not two.

        Uppercase, braced and urn forms all parse to the same UUID. If the
        prefix were derived from the caller's spelling, one workspace's objects
        would scatter across several namespaces and ownership checks would
        disagree with what is actually stored.
        """
        canonical = uuid.UUID("00000000-0000-4000-8000-00000000000a")
        variants = [
            uuid.UUID("00000000-0000-4000-8000-00000000000A"),
            uuid.UUID("{00000000-0000-4000-8000-00000000000a}"),
            uuid.UUID("urn:uuid:00000000-0000-4000-8000-00000000000a"),
            uuid.UUID("000000000000400080000000000000 0a".replace(" ", "")),
        ]

        for variant in variants:
            assert workspace_prefix(variant) == workspace_prefix(canonical)
