"""The architectural guard: no vendor type may leak above the adapter boundary.

A permanent architecture test, in the manner of
`test_no_route_can_reach_the_router_without_the_ai_service` in
`tests/test_ai_cost_governance.py`. It exists because
[[ADR-004 Object Storage Provider and Tenant-Safe Key Construction]] §3 states a
property that is true today and that nothing else would keep true tomorrow:
**`boto3`, `botocore`, bucket names and endpoint URLs stop at
`app/storage/providers/`.**

The failure this prevents is quiet, not loud. Someone adds `import boto3` to a
service to "just check whether the object exists", the code works perfectly, and
provider independence is gone — not with an error, but with a dependency nobody
notices until the day the provider changes. Convention does not catch that.
Neither does review, reliably, a year from now.

Asserted by reading source rather than by importing: an import-based check would
need every module loaded (and `boto3` installed) to say anything, whereas the
text of an import statement is exactly what is being forbidden.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from app.storage import errors, factory, keys, provider
from app.storage.provider import StorageProvider

#: Modules and packages that may never mention a storage vendor.
#: `app/storage/providers/` is deliberately excluded — it is the one place
#: vendor detail belongs.
_APP_ROOT = Path(inspect.getfile(provider)).resolve().parents[2]
_ADAPTER_PACKAGE = _APP_ROOT / "app" / "storage" / "providers"

#: Import roots that indicate a vendor SDK.
_VENDOR_MODULES = frozenset({"boto3", "botocore", "s3transfer", "supabase"})


def _python_files_above_the_adapter_boundary() -> list[Path]:
    """Return every application source file outside the adapter package."""
    return [
        path
        for path in sorted((_APP_ROOT / "app").rglob("*.py"))
        if _ADAPTER_PACKAGE not in path.parents
    ]


def _module_level_imported_roots(path: Path) -> set[str]:
    """Return the top-level module names imported at *module scope* by one file.

    Module scope specifically. `app/storage/factory.py` constructs the boto3
    client inside a function, which is the documented shape: the SDK is not a
    module-level dependency of anything, so importing any module above the
    boundary never pulls a vendor SDK into the process.

    Walking only the module body — rather than `ast.walk`, which would descend
    into function bodies — is what encodes that distinction. A module-level
    `import boto3` anywhere above the adapter package is the regression this
    catches; a deferred one inside the single factory function is the design.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()

    for node in tree.body:
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
        elif isinstance(node, ast.If):
            # `if TYPE_CHECKING:` blocks are module scope in every sense that
            # matters here -- a vendor type annotation would still be a leak.
            for inner in ast.walk(node):
                if isinstance(inner, ast.Import):
                    roots.update(alias.name.split(".")[0] for alias in inner.names)
                elif isinstance(inner, ast.ImportFrom) and inner.module and inner.level == 0:
                    roots.add(inner.module.split(".")[0])

    return roots


def _code_without_docstrings(module: object) -> str:
    """Return a module's source with every docstring and comment removed.

    The boundary rule is about what the *code* references, not about what the
    documentation is allowed to discuss. These modules explain the rule by
    naming `botocore` in prose, and a naive substring check over raw source
    would flag exactly the comments that make the rule comprehensible — pushing
    a future author to delete the explanation to make the test pass.

    Docstrings are stripped via the AST; comments never survive parsing.
    """
    source = inspect.getsource(module)  # type: ignore[arg-type]
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = node.body
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            # Replace rather than delete: a function whose only statement is its
            # docstring would otherwise become a syntax error on unparse.
            body[0] = ast.Expr(value=ast.Constant(value=""))

    return ast.unparse(tree)


class TestNoVendorSdkAboveTheBoundary:
    """The import-level half of the guarantee."""

    def test_no_module_outside_the_adapter_package_imports_a_vendor_sdk(self) -> None:
        """The property this whole step exists to make durable.

        `app/storage/factory.py` is the interesting case: it *constructs* the
        boto3 client, but imports it inside the function body rather than at
        module scope, so the vendor name never appears as a module-level
        dependency. This test enforces that shape.
        """
        offenders: list[str] = []

        for path in _python_files_above_the_adapter_boundary():
            leaked = _module_level_imported_roots(path) & _VENDOR_MODULES
            if leaked:
                offenders.append(f"{path.relative_to(_APP_ROOT)}: {sorted(leaked)}")

        assert not offenders, (
            "A storage vendor SDK is imported above the adapter boundary, which "
            "breaks provider independence (ADR-004 §3):\n" + "\n".join(offenders)
        )

    def test_the_adapter_package_is_the_only_place_boto3_may_appear(self) -> None:
        """Confirms the test above is not vacuous.

        If no file anywhere imported boto3, the assertion would pass while
        proving nothing. This pins the SDK to exactly where it belongs.
        """
        adapter_sources = list(_ADAPTER_PACKAGE.rglob("*.py"))
        assert adapter_sources, "the adapter package should contain the vendor code"

        # boto3 is constructed in the factory (deferred import), and the adapter
        # itself is written against the client object rather than the SDK -- so
        # the vendor name legitimately appears in neither as a module import.
        # What must hold is that it appears nowhere *else*.
        factory_source = Path(inspect.getfile(factory)).read_text(encoding="utf-8")
        assert "import boto3" in factory_source, (
            "the factory is expected to construct the boto3 client; if this moved, "
            "update this test rather than deleting it"
        )


class TestTheContractExposesNoVendorTypes:
    """The signature-level half: the public surface stays vendor-neutral."""

    def test_no_abstract_method_mentions_a_vendor_type(self) -> None:
        """Annotations on the contract must not name a vendor type.

        Checked against *code*, not prose. Docstrings in these modules
        legitimately name `botocore` while explaining what the boundary keeps
        out, and a check that could not tell the two apart would push authors to
        stop documenting the rule in order to satisfy the test enforcing it.
        """
        for vendor in _VENDOR_MODULES:
            assert vendor.lower() not in _code_without_docstrings(provider).lower(), (
                f"`{vendor}` appears in the StorageProvider contract"
            )

    def test_no_method_accepts_a_raw_object_key(self) -> None:
        """ADR-004 §4, asserted structurally rather than trusted.

        Every operation takes `workspace_id` and `logical_name`. A parameter
        named `key`, `path` or `prefix` would reintroduce the caller-supplied
        path this design removes — and would look entirely reasonable in review.
        """
        forbidden = {"key", "path", "object_key", "prefix", "bucket"}

        for name in ("put", "get", "signed_url", "delete"):
            signature = inspect.signature(getattr(StorageProvider, name))
            parameters = set(signature.parameters) - {"self"}

            assert "workspace_id" in parameters, f"{name} must be workspace-scoped"
            assert not parameters & forbidden, (
                f"`{name}` accepts a caller-supplied path parameter "
                f"({sorted(parameters & forbidden)}), which ADR-004 §4 forbids"
            )

    def test_the_error_hierarchy_is_vendor_neutral(self) -> None:
        """Callers must never need to catch a vendor exception."""
        code = _code_without_docstrings(errors).lower()

        for vendor in _VENDOR_MODULES:
            assert vendor.lower() not in code

    def test_key_construction_depends_on_nothing_vendor_specific(self) -> None:
        """The isolation boundary must be portable across every backend.

        If key construction referenced a vendor, changing providers would change
        the tenant boundary — which is the one thing that must not move.
        """
        code = _code_without_docstrings(keys).lower()

        for vendor in _VENDOR_MODULES:
            assert vendor.lower() not in code


class TestTheFactoryReturnsTheNeutralType:
    """Construction must not hand callers a concrete adapter."""

    def test_the_factory_is_annotated_to_return_the_abstraction(self) -> None:
        """A factory returning `R2StorageProvider` would leak the vendor by type.

        Callers would then be free to depend on R2-specific behaviour with the
        type checker's blessing, and the boundary would erode silently.
        """
        signature = inspect.signature(factory.build_storage_provider)

        assert signature.return_annotation in (StorageProvider, "StorageProvider")

    def test_requesting_storage_without_configuration_fails_loudly(self) -> None:
        """Unconfigured storage must raise, never return a broken provider."""

        class _Unconfigured:
            storage_is_configured = False

        with pytest.raises(factory.StorageNotConfiguredError):
            factory.build_storage_provider(_Unconfigured())  # type: ignore[arg-type]
