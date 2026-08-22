/**
 * The explicit theme override, and the script that applies it before paint.
 *
 * ## The three states
 *
 * [[ADR-007 Product Experience Blueprint Authority and Adoption Boundary]]
 * Decision 7 makes the theme cascade three-state rather than two:
 *
 *   1. **No explicit choice** — follow `prefers-color-scheme`.
 *   2. **Explicit light** — light, even on a machine set to dark.
 *   3. **Explicit dark** — dark, even on a machine set to light.
 *
 * States 2 and 3 are carried by a `data-theme` attribute on the document
 * element, which `globals.css` matches with `:root[data-theme="…"]`. State 1
 * is the absence of the attribute.
 *
 * ## Why persistence is client-side only
 *
 * `localStorage` plus the attribute, and nothing else. Storing a theme on the
 * user profile would need an API field, a migration and a write endpoint —
 * API-contract territory that this step does not have and must not invent
 * ([[CLAUDE|CLAUDE.md]] §34).
 *
 * ## What this does NOT do
 *
 * It ships **no appearance control**. Declaring the mechanism does not
 * schedule the surface that drives it: a theme picker is `Proposed` under
 * ADR-007 Decision 3 and enters the product only with an owning step. What
 * exists here is the contract every later control will build on, and the
 * removal of a live defect — native controls, carets, scrollbars and
 * selection rendering light under a full dark token set.
 */

/** Where the explicit choice is persisted. Namespaced so it cannot collide. */
export const THEME_STORAGE_KEY = "projectone-theme";

/** The attribute `globals.css` matches on. Absent means "follow the system". */
export const THEME_ATTRIBUTE = "data-theme";

/** The two values an explicit choice can take. */
export const THEME_CHOICES = ["light", "dark"] as const;

export type ThemeChoice = (typeof THEME_CHOICES)[number];

export function isThemeChoice(value: unknown): value is ThemeChoice {
  return value === "light" || value === "dark";
}

/**
 * The pre-hydration script, as source.
 *
 * ## Why this is a blocking inline script and not a `useEffect`
 *
 * An effect runs *after* the first paint. The user would see the system theme
 * for one frame and their chosen theme for the next — a flash of the wrong
 * theme on every full page load, which is the single most visible defect an
 * explicit theme mechanism can have. The attribute has to be on the element
 * before the first paint, and the only thing that runs that early is a
 * synchronous script in the document.
 *
 * Server rendering cannot do it either: the choice lives in `localStorage`,
 * which the server cannot read, and moving it to a cookie would put a client
 * preference into every request for no gain this step needs.
 *
 * ## Why it swallows its own errors
 *
 * `localStorage` throws rather than returning null in a partitioned or
 * cookie-blocked context. An exception here would be an uncaught error before
 * the app has rendered anything, and the correct fallback — the system theme —
 * is exactly what happens when the attribute is never set. So the failure mode
 * of this script is "the feature is absent", never "the page is broken".
 *
 * Minified by hand rather than by a bundler: it is inlined into the document
 * head as a string, so what is written here is what ships, and it is short
 * enough to read in one pass.
 */
export const THEME_INIT_SCRIPT = `try{var t=localStorage.getItem(${JSON.stringify(
  THEME_STORAGE_KEY,
)});if(t==="light"||t==="dark"){document.documentElement.setAttribute(${JSON.stringify(
  THEME_ATTRIBUTE,
)},t)}}catch(e){}`;
