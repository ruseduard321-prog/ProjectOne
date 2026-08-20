"""The architectural guard on the cross-tenant dispatch path.

A permanent architecture test, in the manner of `test_storage_boundary.py` and
`test_no_ai_call_path_bypasses_governance`. It exists because
[[ADR-005 Async Job Queue and Worker Execution Model]] §5 does not merely
describe a boundary -- it **requires that constraints 1, 3 and 4 be proven by
test rather than by inspection**, on the stated grounds that "a boundary asserted
only in prose is a boundary the next handler's author can cross without
noticing".

The three:

1. **One table.** The dispatcher reads and updates `public.jobs` and nothing
   else. It never joins to a tenant table and never returns tenant data.
3. **The handler never sees a privileged connection.** None is passed to it,
   reachable from it, or held open behind it.
4. **The user's RLS context is established before execution begins.** A handler
   is never invoked outside a tenant-scoped identity.

Constraint 4's *behaviour* is asserted in `test_job_worker.py`, against a real
database, where a revoked member's job is shown never to reach its handler. What
is asserted here is the **structure** that keeps it true: the worker is the only
module that invokes a handler, and it establishes identity before it does.

Asserted by reading source rather than by importing, for the same reason
`test_storage_boundary.py` gives: the text of a statement is exactly what is
being constrained, and an import-based check would need every module loaded to
say anything at all.
"""

from __future__ import annotations

import ast
import inspect
import re
from pathlib import Path

from app.jobs import contract, handlers, registry, service, worker
from app.jobs.contract import ClaimedJob, JobContext
from app.repositories import job_dispatch
from app.workflows import execution

#: tests/ -> api/
_API_ROOT = Path(__file__).resolve().parents[1]
_WORKER_MODULE = _API_ROOT / "app" / "jobs" / "worker.py"

#: Every tenant table the dispatcher must never touch.
#:
#: Written out rather than derived from the migrations, deliberately: a derived
#: list would silently shrink if the derivation broke, and this test would then
#: pass while checking nothing. `test_the_tenant_table_list_is_not_empty` guards
#: the same failure from the other side.
_TENANT_TABLES = frozenset(
    {
        "users",
        "workspaces",
        "workspace_members",
        "projects",
        "assets",
        "conversations",
        "messages",
        "workflow_runs",
        "workflow_step_runs",
        "provider_credentials",
        "ai_budgets",
        "ai_spend_records",
        "ai_shutdown_switches",
        "audit_log",
        "security_event_log",
    }
)


def _code_without_docstrings(module: object) -> str:
    """Return a module's source with every docstring removed.

    The boundary rule is about what the *code* does, not about what the
    documentation may discuss. `job_dispatch.py` names `workspace_members` and
    `AISpendRepository` in prose while explaining the boundary, and a naive
    substring check would flag exactly the comments that make the rule
    comprehensible -- pushing a future author to delete the explanation to make
    the test pass. Comments never survive parsing; docstrings are stripped here.
    """
    tree = ast.parse(inspect.getsource(module))  # type: ignore[arg-type]

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
            # Replaced rather than deleted: a function whose only statement is
            # its docstring would become a syntax error on unparse.
            body[0] = ast.Expr(value=ast.Constant(value=""))

    return ast.unparse(tree)


def _sql_literals(module: object) -> list[str]:
    """Return every string literal in a module's executable code.

    Docstrings are excluded by `_code_without_docstrings`, so what remains is the
    SQL the module actually sends plus a handful of short constants.
    """
    tree = ast.parse(_code_without_docstrings(module))

    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


#: The reconciliation leg's required shape, clause by clause.
#:
#: Each is load-bearing and each is asserted separately, so a statement that
#: loses one fails here rather than in production: the workspace match is what
#: keeps a forged link from writing across a tenant boundary, `deleted_at IS
#: NULL` keeps an erased run erased, and the terminal guard is what stops a
#: dead-letter overwriting a run that already completed or already failed with a
#: more specific reason.
_RECONCILIATION_CLAUSES = (
    "r.workspace_id = s.workspace_id",
    "r.deleted_at IS NULL",
    "r.status NOT IN ('completed', 'failed')",
    "RETURNING r.id",
)


def _statements_naming(module: object, table: str) -> list[str]:
    """Return every SQL literal in `module` that names `table`."""
    pattern = rf"\b(public\.)?{table}\b"

    return [literal for literal in _sql_literals(module) if re.search(pattern, literal.lower())]


class TestConstraintOneTwoTables:
    """ADR-005 §5 constraint 1, as [[ADR-006]] D6 restates it.

    **The bound widened by exactly one statement shape, and this class is what
    holds it there.** The dispatcher may now update `public.workflow_runs` in
    the reconciliation leg of its two dead-letter paths -- and in nothing else.
    The count is asserted, so a third statement naming the table fails the
    build, and so does deleting one.
    """

    def test_no_statement_mentions_a_tenant_table(self) -> None:
        """Every tenant table except `workflow_runs` appears zero times.

        `workflow_runs` has its own tests below, which are stricter than this
        one rather than an exemption from it: this asserts absence, and those
        assert an exact count and an exact shape.
        """
        offenders: list[str] = []

        for table in _TENANT_TABLES - {"workflow_runs"}:
            for literal in _statements_naming(job_dispatch, table):
                offenders.append(f"{table}: {' '.join(literal.split())[:80]}")

        assert not offenders, (
            "The job dispatcher references a tenant table. ADR-005 §5 constraint 1, "
            "as restated by ADR-006 D6, bounds the privileged path to `public.jobs` "
            "plus one `workflow_runs` UPDATE — a join here is a cross-tenant read "
            "that no route test would catch:\n" + "\n".join(offenders)
        )

    def test_the_step_table_is_never_named(self) -> None:
        """`workflow_step_runs` appears **zero** times, and that is load-bearing.

        Reconciliation must never clear a step claim. The stale claim is the
        evidence of what was in flight, the live fence against the worker that
        took it, and the only thing standing between the next delivery and a
        provider that has already been paid (ADR-006 D5, I10). A dispatcher that
        could reach that table could undo all three.
        """
        assert _statements_naming(job_dispatch, "workflow_step_runs") == []

    def test_exactly_two_statements_name_the_run_table(self) -> None:
        """Two dead-letter paths, two reconciliation legs, and no third.

        The reap inside `claim` and the terminal branch of `record_outcome`.
        **The count is the assertion**: deleting either leg fails this test, and
        so does adding a statement that reaches the run table for any other
        reason.
        """
        naming = _statements_naming(job_dispatch, "workflow_runs")

        assert len(naming) == 2, (
            f"{len(naming)} dispatcher statements name public.workflow_runs; "
            "ADR-006 D6 permits exactly two — the reap leg and the settle leg"
        )

    def test_each_run_statement_is_a_guarded_update_returning_only_an_id(self) -> None:
        """The shape, clause by clause, on both legs.

        An UPDATE, matched on the job's own workspace, skipping erased runs,
        never overwriting a terminal one, and returning `r.id` and nothing else.
        A reconciliation returning a run's `detail` or `triggered_by` would be a
        cross-tenant read wearing an UPDATE's clothes.
        """
        for literal in _statements_naming(job_dispatch, "workflow_runs"):
            collapsed = " ".join(literal.split())

            assert "UPDATE public.workflow_runs r" in collapsed, (
                f"a run statement is not the accepted UPDATE: {collapsed[:120]}"
            )

            for clause in _RECONCILIATION_CLAUSES:
                assert clause in collapsed, (
                    f"the reconciliation leg is missing `{clause}`: {collapsed[:200]}"
                )

    def test_no_statement_reads_the_run_table(self) -> None:
        """Never a `SELECT`. The dispatcher writes a terminal state and reads nothing.

        A read would return tenant data across the boundary; the widening ADR-006
        accepted is a write that returns one id.
        """
        for literal in _sql_literals(job_dispatch):
            collapsed = " ".join(literal.split()).lower()

            assert not re.search(r"select\b[^;]*?\bfrom\s+(public\.)?workflow_runs\b", collapsed), (
                f"a dispatcher statement reads public.workflow_runs: {collapsed[:120]}"
            )

    def test_every_statement_names_the_jobs_table(self) -> None:
        """The queue is still what the dispatcher is for.

        Every statement it sends touches `public.jobs`; the run table is only
        ever reached from a row that statement just settled.
        """
        statements = [
            literal
            for literal in _sql_literals(job_dispatch)
            if "SELECT" in literal or "UPDATE" in literal
        ]

        assert statements, "the dispatcher sends no SQL; this guard would be vacuous"

        for statement in statements:
            assert "public.jobs" in statement, (
                f"a dispatcher statement does not name public.jobs: {statement[:120]}"
            )

    def test_the_tenant_table_list_is_not_empty(self) -> None:
        """A shrinking list would make every test above quietly weaker."""
        assert len(_TENANT_TABLES) >= 15, (
            "_TENANT_TABLES has shrunk. If a table was genuinely dropped, remove it "
            "deliberately — do not clear the list to make this file quiet."
        )


class TestConstraintThreeNoPrivilegedConnection:
    """Nothing a handler can reach opens a connection that bypasses RLS."""

    def test_the_claim_carries_no_connection(self) -> None:
        """`ClaimedJob` is an identity, not a handle.

        ADR-005 §5 constraint 3 is written as "passed to, reachable from, **or
        held open during**" handler code, and this is the first of the three: a
        connection or a DSN on the claim would be reachable by definition.
        """
        forbidden = {"connection", "cursor", "dsn", "database_url", "settings", "session"}
        fields = set(ClaimedJob.__dataclass_fields__)

        assert not fields & forbidden, (
            f"ClaimedJob exposes {sorted(fields & forbidden)}; the dispatcher hands "
            "the worker an identity, never a connection"
        )

    def test_the_handler_context_exposes_only_a_tenant_session(self) -> None:
        """`JobContext` is the entire surface a handler is given.

        A `settings` or a `dispatch` field here would let a handler open a
        privileged connection of its own, which is the same breach by a longer
        route.
        """
        forbidden = {"connection", "cursor", "dsn", "database_url", "settings", "dispatch"}
        fields = set(JobContext.__dataclass_fields__)

        assert "tenant_session" in fields, "a handler must have a way to reach the database"

        # New in STEP-31, and deliberately not on the forbidden list. A lease
        # token is an opaque identifier that opens nothing: it grants no access
        # and names no data, and what it buys is the ability to put "do I still
        # hold this job?" inside a database predicate (ADR-006 D8).
        assert "lease_token" in fields
        assert "workflow_run_id" in fields

        assert not fields & forbidden, (
            f"JobContext exposes {sorted(fields & forbidden)}; a handler must reach "
            "the database only through an RLS-subject session"
        )

    def test_no_handler_module_can_reach_the_dispatcher_or_the_settings(self) -> None:
        """Handlers import the contract, and nothing that opens a connection.

        The import-level half. A handler that imported `JobDispatchRepository`
        or `Settings` could construct a privileged connection and every query it
        then ran would look entirely ordinary at the call site.
        """
        source = _code_without_docstrings(handlers)

        for forbidden in (
            "JobDispatchRepository",
            "job_dispatch",
            "get_settings",
            "psycopg.connect",
        ):
            assert forbidden not in source, (
                f"app/jobs/handlers.py references `{forbidden}`; a handler must not be "
                "able to open a connection of its own (ADR-005 §5 constraint 3)"
            )

    def test_the_composition_module_opens_no_connection_of_its_own(self) -> None:
        """The one module that holds `Settings` on the worker's behalf is bounded too.

        A handler is *given* a definitions factory rather than building one,
        because building one needs configuration a handler must not be able to
        reach. That configuration has to live somewhere, and it lives in
        `app/workflows/execution.py` -- so the boundary moves there rather than
        disappearing.

        What it may do: construct services against a connection **it was
        handed**. What it may not: open one, or reach the privileged dispatcher.
        """
        source = _code_without_docstrings(execution)

        for forbidden in ("JobDispatchRepository", "job_dispatch", "psycopg.connect"):
            assert forbidden not in source, (
                f"app/workflows/execution.py references `{forbidden}`; the worker's "
                "composition root may build services, never connections"
            )

    def test_the_dispatcher_closes_its_connection_on_every_path(self) -> None:
        """ "Held open during handler code" is the half a signature cannot carry.

        `_connect` closes in a `finally`, so the connection's lifetime ends with
        the statement rather than with the worker. A future change to a pooled or
        long-lived connection would break constraint 3 while every other
        assertion here still passed.
        """
        source = _code_without_docstrings(job_dispatch)

        assert "finally:" in source and "connection.close()" in source, (
            "JobDispatchRepository._connect must close its connection on every exit "
            "path, or a privileged connection can outlive the statement that needed it"
        )


class TestConstraintFourIdentityBeforeExecution:
    """A handler is never invoked outside an established tenant identity."""

    def test_the_worker_is_the_only_module_that_invokes_a_handler(self) -> None:
        """One invocation site, so one place has to get the ordering right.

        A second caller of `handler.execute(...)` anywhere would be a second
        place constraint 4 could be violated, and it would not look wrong.
        """
        invokers: list[str] = []

        for path in sorted((_API_ROOT / "app").rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "execute"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "handler"
                ):
                    invokers.append(str(path.relative_to(_API_ROOT)))

        assert invokers == ["app/jobs/worker.py"], (
            f"handlers are invoked from {sorted(set(invokers))}; ADR-005 §5 constraint 4 "
            "is an ordering guarantee, and it can only be guaranteed in one place"
        )

    def test_identity_is_established_before_the_handler_runs(self) -> None:
        """The ordering itself, read off the worker's own call sequence.

        `_process` calls `_establish_identity` and *then* `_execute`. Reversing
        the two lines would leave every behavioural test passing for a valid
        actor while removing the guarantee entirely for a revoked one -- and the
        revoked case is the one that matters.
        """
        tree = ast.parse(_WORKER_MODULE.read_text(encoding="utf-8"))
        process = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "_process"
        )

        called = [
            node.func.attr
            for node in ast.walk(process)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        ]

        assert "_establish_identity" in called and "_execute" in called
        assert called.index("_establish_identity") < called.index("_execute"), (
            "the worker executes a handler before establishing tenant identity"
        )

    def test_the_worker_opens_tenant_sessions_only_through_the_request_factory(self) -> None:
        """`authenticated_as` is the only door, so the role switch cannot be skipped.

        A worker-specific session helper would be a second implementation of the
        tenant boundary -- and the reason ADR-005 §4 reuses this one is that
        forgetting the role switch here fails *closed*, because `projectone_api`
        is `NOINHERIT`.
        """
        source = _code_without_docstrings(worker)

        assert "authenticated_as" in source
        assert "psycopg.connect" not in source, (
            "the worker opens a connection directly; every tenant session must come "
            "from RequestSessionFactory.authenticated_as"
        )


class TestTheContractStatesItsGuarantee:
    """At-least-once is stated where a handler author will read it."""

    def test_the_contract_docstring_states_the_delivery_guarantee(self) -> None:
        """ADR-005 §6 requires this in the contract's *own* docstring.

        Not decoration: the ADR's reasoning is that "a handler author who has to
        infer the delivery guarantee will infer the convenient one". A contract
        that stopped saying so would be a contract people got wrong.
        """
        docstring = contract.__doc__ or ""

        assert "at-least-once" in docstring.lower()
        assert "twice" in docstring.lower(), (
            "the docstring should say plainly that a handler will eventually run twice"
        )

    def test_the_enqueue_path_never_reaches_the_dispatcher(self) -> None:
        """Nothing on the request path may claim, lease or settle a job.

        The API enqueues and reads; the worker dispatches. A route able to claim
        a job would be a route able to run tenant work outside a worker's
        identity handling.
        """
        for module in (service, registry, handlers):
            source = _code_without_docstrings(module)
            assert "JobDispatchRepository" not in source, (
                f"{module.__name__} reaches the dispatcher; the privileged path belongs "
                "to the worker alone"
            )
