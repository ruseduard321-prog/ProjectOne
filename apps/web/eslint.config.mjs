import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    // Playwright's own output. Git ignores both, but a flat config does not
    // read .gitignore — and `--max-warnings=0` means a local lint run after a
    // browser run would otherwise fail on generated report bundles.
    "playwright-report/**",
    "test-results/**",
  ]),
]);

export default eslintConfig;
