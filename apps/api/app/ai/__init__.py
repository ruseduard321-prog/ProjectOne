"""The provider-agnostic AI layer.

Deliberately importable without importing FastAPI, psycopg or any vendor SDK:
the abstraction, the router, the health breaker and the error hierarchy are
framework-agnostic by construction.

That property is what would let this move to `packages/` if a second application
ever needs it. It has **not** been moved, because introducing the first shared
package is a structural decision belonging to the owner rather than a side
effect of this step (CLAUDE.md §8) -- and a package with exactly one consumer is
indirection without a benefit. The constraint is kept so the option stays open.
"""
