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


#: The **composition root**: the single module permitted to import a vendor SDK
#: outside the adapter package, because something has to construct the client.
#:
#: Narrow on purpose. It is one file, named explicitly rather than matched by a
#: pattern, and it is the only exemption -- adding a second one is a decision
#: someone has to make deliberately by editing this constant, which is exactly
#: the friction an architectural boundary should have.
_COMPOSITION_ROOT = _APP_ROOT / "app" / "storage" / "factory.py"


def _vendor_references_at_any_depth(path: Path) -> set[str]:
    """Return vendor module names imported anywhere in one file, at any depth.

    **Any depth is the point.** An earlier version of this guard walked only
    `tree.body`, which meant a module-scope `import boto3` failed the build
    while the same import placed inside a function body passed it:

        def check_exists(...):
            import boto3          # invisible to a module-scope-only scan
            ...

    That is not a hypothetical shape -- deferring an import inside a function is
    a normal Python idiom for avoiding a startup cost, so the loophole would
    have been opened by someone following good practice for an unrelated reason,
    not by someone circumventing the rule. A guard that only catches the obvious
    spelling of a violation provides confidence rather than protection.

    `ast.walk` visits every node, so a vendor import is caught wherever it is
    written: module scope, function body, method, nested function, `try` block
    or `if TYPE_CHECKING`. `importlib.import_module("boto3")` and similar
    dynamic forms are caught by `_dynamic_vendor_references` below.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])

    return roots & _VENDOR_MODULES


def _dynamic_vendor_references(path: Path) -> set[str]:
    """Return vendor names reached through a dynamic import in one file.

    `import boto3` is not the only spelling. `importlib.import_module("boto3")`
    and `__import__("boto3")` both produce the module without an `ast.Import`
    node anywhere, so a guard checking only import statements would wave them
    through -- and a reviewer scanning for the word "import" would too.

    Only string-literal arguments are detected. A fully computed module name is
    beyond static analysis, and pretending otherwise would give this guard a
    reassuring but false completeness; what it does catch is every form anyone
    would plausibly write on purpose.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func = node.func
        is_dynamic_import = (isinstance(func, ast.Name) and func.id == "__import__") or (
            isinstance(func, ast.Attribute) and func.attr == "import_module"
        )
        if not is_dynamic_import:
            continue

        for argument in node.args:
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                root = argument.value.split(".")[0]
                if root in _VENDOR_MODULES:
                    found.add(root)

    return found


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
    """The import-level half of the guarantee, at any nesting depth."""

    def test_no_module_above_the_boundary_references_a_vendor_sdk(self) -> None:
        """The property this whole step exists to make durable.

        Checked at **any depth**, so a vendor import hidden inside a function
        body fails exactly like one at module scope. Only the composition root
        is exempt, and only because something must construct the client.
        """
        offenders: list[str] = []

        for path in _python_files_above_the_adapter_boundary():
            if path == _COMPOSITION_ROOT:
                continue
            leaked = _vendor_references_at_any_depth(path) | _dynamic_vendor_references(path)
            if leaked:
                offenders.append(f"{path.relative_to(_APP_ROOT)}: {sorted(leaked)}")

        assert not offenders, (
            "A storage vendor SDK is referenced above the adapter boundary, which "
            "breaks provider independence (ADR-004 §3). Vendor SDKs belong in "
            "app/storage/providers/, and only app/storage/factory.py may "
            "construct the client:\n" + "\n".join(offenders)
        )

    def test_the_composition_root_exemption_stays_narrow(self) -> None:
        """The exemption must cover one file and one SDK, not a category.

        An exemption nobody re-examines becomes a hole. Pinning both the file
        and what it is allowed to reach means widening it requires editing this
        test, which puts the decision in front of a reviewer.
        """
        assert _COMPOSITION_ROOT.exists()
        assert _COMPOSITION_ROOT == _APP_ROOT / "app" / "storage" / "factory.py"

        # The one exempt file may reach boto3 -- and nothing else on the list.
        referenced = _vendor_references_at_any_depth(_COMPOSITION_ROOT)
        assert referenced == {"boto3"}, (
            f"the composition root references {sorted(referenced)}; it is exempt "
            "only for constructing the boto3 client"
        )

    def test_the_guard_is_not_vacuous(self) -> None:
        """Confirms the scan actually finds vendor imports when they exist.

        If `_vendor_references_at_any_depth` were broken -- a bad parse, an
        empty file list -- every assertion above would pass while checking
        nothing. This proves the detector detects.

        Both negative controls are exercised as *source text*, so the check runs
        against the same code path the real scan uses without writing a
        violation into the repository.
        """
        module_level = "import boto3\n\n\ndef f() -> None:\n    pass\n"
        function_local = "def f() -> None:\n    import boto3\n\n    return boto3\n"
        dynamic = "import importlib\n\n\ndef f():\n    return importlib.import_module('boto3')\n"

        scratch = _APP_ROOT / "_boundary_negative_control.py"
        for label, source in (
            ("module-level", module_level),
            ("function-local", function_local),
        ):
            scratch.write_text(source, encoding="utf-8")
            try:
                assert _vendor_references_at_any_depth(scratch) == {"boto3"}, (
                    f"the guard failed to detect a {label} vendor import"
                )
            finally:
                scratch.unlink()

        scratch.write_text(dynamic, encoding="utf-8")
        try:
            assert _dynamic_vendor_references(scratch) == {"boto3"}, (
                "the guard failed to detect a dynamic vendor import"
            )
        finally:
            scratch.unlink()

    def test_the_adapter_package_actually_contains_the_vendor_code(self) -> None:
        """The SDK must live somewhere, and that somewhere is the adapter side."""
        assert list(_ADAPTER_PACKAGE.rglob("*.py")), (
            "the adapter package should contain the vendor code"
        )

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
