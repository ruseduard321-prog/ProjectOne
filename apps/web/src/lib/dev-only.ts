/**
 * The production exclusion for development-only routes.
 *
 * ## Why this is the most important file in STEP-16a
 *
 * A page reporting session state, proxy headers and backend connectivity is a
 * reconnaissance surface if it ever answers in production. The feature's entire
 * risk is its exclusion, not its content — so the requirement is inverted from
 * a normal feature: the hardest thing to prove is that the route is *absent*,
 * not that it renders.
 *
 * ## Two mechanisms, deliberately
 *
 * One mechanism is one mistake away from failing.
 *
 *  1. **Never prerendered.** The route exports `dynamic = "force-dynamic"`, so
 *     no session state is baked into a build artifact and the runtime check
 *     below actually runs on every request rather than being answered from a
 *     cached static page. That export must be a **static string literal** in
 *     the route file — Next.js parses it at compile time and rejects any
 *     indirection, including an imported constant, which is why this module
 *     does not supply it.
 *  2. **Runtime refusal.** {@link notFoundInProduction} calls `notFound()` when
 *     `NODE_ENV` is `production`, so even a build that somehow included the
 *     route refuses to serve it.
 *
 * **404, never 403.** A 403 confirms the route exists, which tells a prober
 * exactly where to keep looking. A 404 is indistinguishable from a path that
 * was never built.
 *
 * ## Why `NODE_ENV` rather than the app's own environment variable
 *
 * `NEXT_PUBLIC_PROJECTONE_ENVIRONMENT` is configuration — a value someone sets,
 * and therefore a value someone can set wrongly. `NODE_ENV` is set to
 * `production` by `next build` and `next start` themselves, so it is a property
 * of how the application was built rather than of how it was configured. For a
 * control whose failure mode is "diagnostics served to the internet", the
 * signal that cannot be misconfigured is the right one.
 *
 * Both are checked, in fact: a staging deploy is `NODE_ENV=production` and is
 * correctly refused, and a development build explicitly configured as
 * production is refused too.
 */

/**
 * Path prefixes reserved for development-only routes.
 *
 * A prefix rather than a list of exact paths, so a second inspector page added
 * later inherits the exclusion instead of needing to remember it. Forgetting
 * would mean shipping a diagnostics page to production, which is precisely the
 * failure this module exists to prevent.
 */
const DEV_ONLY_PREFIX = "/dev";

/** Whether `pathname` belongs to the development-only namespace. */
export function isDevOnlyPath(pathname: string): boolean {
  return pathname === DEV_ONLY_PREFIX || pathname.startsWith(`${DEV_ONLY_PREFIX}/`);
}

/**
 * Whether development-only routes may be served in this process.
 *
 * Not exported for use as a *conditional render* — a page that renders a
 * reduced view in production is still a page that answers in production. It
 * exists so the proxy and the page can share one decision, and so tests can
 * assert it directly.
 *
 * **No `next/navigation` import in this module.** The proxy runs on the Edge
 * runtime, which does not provide it; keeping this file dependency-free is
 * what lets both runtimes share the same decision rather than each keeping
 * their own copy of it.
 */
export function devRoutesEnabled(): boolean {
  if (process.env.NODE_ENV === "production") {
    return false;
  }

  return process.env.NEXT_PUBLIC_PROJECTONE_ENVIRONMENT !== "production";
}

/**
 * Refuse the request unless this is a development build.
 *
 * Call this **first** in a development-only page, before reading cookies,
 * calling the API, or touching anything else — the work then never happens in
 * a production process rather than happening and being discarded.
 *
 * **This is the second line, not the first.** It cannot set a 404 status on
 * its own: the root `loading.tsx` Suspense boundary flushes a 200 before a
 * page body runs, so `notFound()` here renders the not-found *body* inside a
 * 200 response. Verified directly against a production build. The proxy is
 * what returns the real 404, and this remains because a page that somehow
 * bypassed the proxy must still refuse to do the work.
 *
 * `notFound` is imported lazily so this module stays free of `next/navigation`,
 * which the Edge runtime the proxy uses does not provide.
 */
export async function notFoundInProduction(): Promise<void> {
  if (devRoutesEnabled()) {
    return;
  }

  const { notFound } = await import("next/navigation");

  notFound();
}
