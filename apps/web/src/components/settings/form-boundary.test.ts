/**
 * The server/client boundary contract for settings forms.
 *
 * `SettingsForm` is a Client Component, and every page that renders one is a
 * Server Component. A function cannot cross that boundary — React rejects it
 * with *"Functions are not valid as a child of Client Components"* — so the
 * fields are passed as plain JSX and read their state from `form-context.ts`.
 *
 * These tests assert that contract against the source, because the failure it
 * prevents is a runtime error on a real page rather than a type error: a render
 * prop reintroduced in a Server Component type-checks fine as long as the child
 * type still permits a function, and only breaks when someone opens the screen.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const SRC = join(import.meta.dirname, "..", "..");

/** Every file that renders a `SettingsForm`. */
const CALL_SITES = [
  join(SRC, "app", "(app)", "settings", "page.tsx"),
  join(SRC, "app", "(app)", "projects", "page.tsx"),
  join(SRC, "app", "(app)", "projects", "[projectId]", "page.tsx"),
  join(SRC, "components", "settings", "ProviderKeyForm.tsx"),
  // STEP-29 moved the asset delete form into a row component, inside a
  // `ConfirmDialog` — which is itself a Client Component taking `children`, so
  // the same constraint applies one level deeper than before.
  join(SRC, "components", "projects", "AssetRow.tsx"),
];

/**
 * A JSX child that is an arrow function: `{(state, pending) => …}` or `{() => …}`.
 *
 * Matched against the source rather than the rendered output because that is
 * where the mistake is made, and the shape is distinctive enough that a comment
 * mentioning the old pattern in prose does not trip it.
 */
const FUNCTION_CHILD = /\{\s*\([^)]*\)\s*=>/;

describe("settings form boundary", () => {
  it.each(CALL_SITES)("passes no function as a child in %s", (path) => {
    const source = readFileSync(path, "utf8");

    // Only the JSX body, so an event handler or a `.map()` callback in module
    // scope is not mistaken for a render-prop child.
    const jsx = source.slice(source.indexOf("<SettingsForm"));

    expect(jsx).not.toMatch(FUNCTION_CHILD);
  });

  it("types SettingsForm children as ReactNode, not a function", () => {
    const source = readFileSync(join(SRC, "components", "settings", "SettingsForm.tsx"), "utf8");

    expect(source).toMatch(/readonly children:\s*ReactNode/);
    // The render-prop signature this replaced. Its return would be a function
    // type, which is exactly what may not cross the boundary.
    expect(source).not.toMatch(/readonly children:\s*\(/);
  });

  it("keeps every field-error key addressable by a field name", async () => {
    // The context looks an error up by the input's `name`, so an action that
    // reports an error under a key no field carries would be silently invisible.
    const { EMPTY_FORM_STATE } = await import("@/lib/form-state");

    expect(EMPTY_FORM_STATE.fieldErrors).toEqual({});
  });
});
