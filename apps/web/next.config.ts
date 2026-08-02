import type { NextConfig } from "next";

/**
 * Whether development-only routes are compiled into this build.
 *
 * Mirrors the runtime decision in `src/lib/dev-only.ts` and deliberately does
 * not import it: this file is evaluated by the Next.js build process before
 * TypeScript path aliases resolve. Duplicating one boolean expression is
 * cheaper than the indirection required to share it, and
 * `src/lib/dev-only.test.ts` asserts the two agree.
 */
const devRoutesEnabled =
  process.env.NODE_ENV !== "production" &&
  process.env.NEXT_PUBLIC_PROJECTONE_ENVIRONMENT !== "production";

/**
 * Page extensions this build recognises.
 *
 * This is the **build-time half** of the `/dev/*` exclusion (STEP-16a).
 *
 * Development-only route files are named `page.dev.tsx`. A production build
 * omits that extension, so Next.js does not treat those files as routes at
 * all: they are never compiled, never enter the route manifest, and cannot be
 * served by any means. A development build adds it back.
 *
 * Why two mechanisms rather than one. The runtime refusal in `src/proxy.ts`
 * depends on `NODE_ENV` being right at *run* time; this one depends on it at
 * *build* time. Either alone is one misconfiguration away from serving session
 * diagnostics to the internet, which is the entire risk of the feature.
 * Neither is the "real" check — they fail independently, which is the point.
 */
const pageExtensions = ["tsx", "ts", "jsx", "js"];

if (devRoutesEnabled) {
  // Ahead of "tsx" so `page.dev.tsx` is matched on its longer extension first;
  // otherwise Next.js resolves it as a page literally named `page.dev`.
  pageExtensions.unshift("dev.tsx");
}

const nextConfig: NextConfig = {
  pageExtensions,
};

export default nextConfig;
