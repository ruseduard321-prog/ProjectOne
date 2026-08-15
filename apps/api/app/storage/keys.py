"""Tenant-scoped object key construction — the storage layer's isolation boundary.

Everywhere else in ProjectOne the workspace boundary is enforced by the database:
Row Level Security refuses the row, so a repository that forgot its filter is
still safe (CLAUDE.md §16). **Object storage has no equivalent.** A bucket is a
flat key space and a key is just a string, so whatever isolation exists is the
isolation this module constructs.

That makes this the one module in the storage package where a defect is a
cross-tenant data leak with no second line of defence
([[ADR-004 Object Storage Provider and Tenant-Safe Key Construction]] §5).

## Why callers cannot supply a key

`StorageProvider` accepts a workspace id and a *logical name*, never a path. An
interface that accepted a raw key could not be made safe by documentation: the
first caller to interpolate user input into it would reintroduce every traversal
bug this module exists to prevent, and it would look perfectly ordinary at the
call site.

So there is no public function here that turns an arbitrary string into a key.
`build_object_key` is the only constructor, and it validates both halves.

## Why the workspace segment is a UUID, not a caller-chosen string

The workspace id is typed `uuid.UUID` rather than `str` throughout this module.
That single choice eliminates an entire class of attack before any validation
runs: a `UUID` cannot contain `/`, `..`, `%2f`, a null byte, or a leading `/`,
because the type will not hold those characters at all. A hostile *workspace
identifier* is therefore not a string this module has to defend against — it is
a value that never constructs.

This is deliberate defence by construction rather than by filtering. Validation
below still runs, because the logical name genuinely is caller-supplied.

## Why a trailing delimiter on the workspace prefix

`ws/{uuid}/` — with the trailing slash — is the prefix for a workspace, and the
slash is load-bearing. Without it, prefix comparison is wrong by construction:
`ws-1` is a prefix of `ws-10`, so any ownership check that asks "does this key
start with this workspace's prefix?" would answer yes for a *different*
workspace's object. UUIDs make the collision unlikely rather than impossible to
reason about, and "unlikely" is not an isolation guarantee.

Terminating the prefix with the delimiter makes containment exact: `ws/{a}/` can
never prefix `ws/{b}/` for `a != b`, whatever the two ids are. `key_belongs_to`
relies on this, and `test_storage_keys.py` proves the `ws-1`/`ws-10` case
directly against it.
"""

from __future__ import annotations

import posixpath
import re
import unicodedata
import urllib.parse
import uuid

#: Separates key segments. Object stores are flat key spaces, but every S3
#: compatible implementation treats `/` as the hierarchy delimiter for prefix
#: listing, so it is the delimiter here too.
DELIMITER = "/"

#: Namespace root for workspace-owned objects. Everything this module can
#: construct sits under it, which leaves room for non-tenant objects later
#: without a migration of the key space.
_WORKSPACE_ROOT = "ws"

#: The maximum length of a logical name. Well below S3's 1024-byte key limit,
#: leaving room for the prefix and keeping keys readable in a console.
MAX_LOGICAL_NAME_LENGTH = 200

#: Characters a logical name may contain: ASCII alphanumerics, dot, hyphen,
#: underscore. An **allowlist**, deliberately.
#:
#: A denylist of dangerous characters is the wrong shape for this problem. It
#: has to anticipate every encoding of every separator on every platform --
#: `/`, `\`, `%2f`, `%252f`, `∕`, a null byte truncating a C-level path --
#: and it silently fails open on the one nobody thought of. An allowlist fails
#: closed on anything unanticipated, which is the only safe default for a
#: boundary with no second line of defence (CLAUDE.md §16).
_LOGICAL_NAME_PATTERN = re.compile(r"\A[A-Za-z0-9._-]+\Z")


class InvalidLogicalNameError(ValueError):
    """A caller-supplied logical name is not usable as a key segment.

    A `ValueError` subclass rather than a bespoke hierarchy: this is a rejected
    argument, and the callers that need to distinguish it (a future upload
    endpoint mapping it to a 4xx) can catch this type specifically.

    The message never echoes the rejected value. A name is caller-controlled
    input, and reflecting it into an error that may reach a log or an HTTP
    response is how an injection becomes a second vulnerability
    (CLAUDE.md §24 -- user-facing messages stay free of implementation detail).
    """

    def __init__(self, reason: str) -> None:
        """Initialise the error from a reason that never echoes the input."""
        super().__init__(f"Invalid storage object name: {reason}")
        #: Safe to surface to an API caller: describes the rule, not the input.
        self.public_message = f"Invalid storage object name: {reason}"


def workspace_prefix(workspace_id: uuid.UUID) -> str:
    """Return the key prefix owning every object of one workspace.

    Always terminated by `DELIMITER`. That is what makes prefix containment
    exact rather than merely probable -- see this module's docstring.

    Args:
        workspace_id: The workspace whose namespace is being addressed.

    Returns:
        A prefix of the form `ws/{workspace_id}/`.
    """
    # `str(UUID)` is canonical lowercase hyphenated form regardless of how the
    # UUID was parsed, so two spellings of the same id cannot produce two
    # prefixes -- which would split one workspace's objects across two
    # namespaces and make ownership checks disagree with storage reality.
    return f"{_WORKSPACE_ROOT}{DELIMITER}{workspace_id}{DELIMITER}"


def _reject_unsafe_logical_name(logical_name: str) -> None:
    """Raise unless `logical_name` is a single, safe path segment.

    Ordered cheapest-check-first, but every check is independent: none of them
    is load-bearing alone, and the allowlist at the end is what actually closes
    the set. The earlier checks exist to produce an accurate reason rather than
    a generic one, which matters when a legitimate caller hits the rule.
    """
    if not logical_name:
        raise InvalidLogicalNameError("it must not be empty")

    if len(logical_name) > MAX_LOGICAL_NAME_LENGTH:
        raise InvalidLogicalNameError(f"it must be at most {MAX_LOGICAL_NAME_LENGTH} characters")

    # Unicode normalisation before inspection. Without it, a name could carry
    # characters that are canonically equivalent to a separator, pass a naive
    # check in one form, and be normalised into the dangerous form by something
    # downstream. NFKC folds those representations together first.
    if unicodedata.normalize("NFKC", logical_name) != logical_name:
        raise InvalidLogicalNameError("it must be Unicode-normalised (NFKC)")

    # Percent-decoding is checked *before* the allowlist, so that a name which
    # would decode into a separator is rejected with an accurate reason. The
    # allowlist would reject `%` anyway; this makes the intent explicit and the
    # test for encoded separators assert against the rule it is really testing.
    if logical_name != urllib.parse.unquote(logical_name):
        raise InvalidLogicalNameError("it must not contain percent-encoded characters")

    if "\x00" in logical_name:
        raise InvalidLogicalNameError("it must not contain a null byte")

    # Explicit separator and traversal checks. Redundant against the allowlist
    # by design: this is the property the module exists to guarantee, so it is
    # asserted directly rather than left as a consequence of a regex someone
    # might later widen.
    if DELIMITER in logical_name or "\\" in logical_name:
        raise InvalidLogicalNameError("it must not contain a path separator")

    if logical_name in (".", "..") or logical_name.startswith(".."):
        raise InvalidLogicalNameError("it must not be a path traversal segment")

    if not _LOGICAL_NAME_PATTERN.match(logical_name):
        raise InvalidLogicalNameError(
            "it may contain only letters, digits, dot, hyphen and underscore"
        )


def build_object_key(workspace_id: uuid.UUID, logical_name: str) -> str:
    """Build the object key for one workspace's logical object.

    **The only way an object key is constructed in ProjectOne.** No caller
    passes a key, and no other function returns one
    ([[ADR-004 Object Storage Provider and Tenant-Safe Key Construction]] §4).

    Args:
        workspace_id: The owning workspace. A `UUID`, so a hostile workspace
            identifier is unrepresentable rather than filtered.
        logical_name: The caller's name for the object, validated as a single
            safe path segment.

    Returns:
        A key of the form `ws/{workspace_id}/{logical_name}`.

    Raises:
        InvalidLogicalNameError: if `logical_name` is not a safe single segment.
    """
    _reject_unsafe_logical_name(logical_name)

    key = f"{workspace_prefix(workspace_id)}{logical_name}"

    # A final assertion that construction landed inside the intended namespace.
    # `normpath` collapses any `.`/`..` that survived validation; if the result
    # differs, something got through and the safe response is to refuse rather
    # than to return a key that was *nearly* right (CLAUDE.md §24 -- fail
    # closed, never silently).
    if posixpath.normpath(key) != key or not key.startswith(workspace_prefix(workspace_id)):
        raise InvalidLogicalNameError("it does not resolve to a workspace-scoped key")

    return key


def key_belongs_to(key: str, workspace_id: uuid.UUID) -> bool:
    """Return whether `key` lies inside `workspace_id`'s namespace.

    Used to fail **closed** on any operation naming an object the workspace does
    not own. Comparison is against the delimiter-terminated prefix, which is
    what makes `ws/{a}/` unable to match `ws/{b}/` -- the prefix-confusion case
    (`ws-1` vs `ws-10`) that a naive `startswith` on an unterminated prefix gets
    wrong.

    Args:
        key: The object key under test.
        workspace_id: The workspace claiming it.

    Returns:
        True only if the key is owned by that workspace.
    """
    return key.startswith(workspace_prefix(workspace_id))
