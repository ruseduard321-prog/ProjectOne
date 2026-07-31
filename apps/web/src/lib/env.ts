/**
 * Validated environment configuration for the web application.
 *
 * Parsed once at module load, so a missing or malformed variable stops the
 * process at startup with a message naming it — never as a confusing failure
 * inside a request handler later (CLAUDE.md §28a).
 *
 * Written in plain TypeScript rather than pulling in a schema library. The
 * rules here are a handful of string checks; a new dependency for that would
 * be added surface area for no gain (CLAUDE.md §28).
 *
 * Import `env` from this module. Never read `process.env` directly elsewhere —
 * that bypasses validation and re-introduces the untyped access this exists to
 * remove.
 */

export const ENVIRONMENTS = ["development", "staging", "production"] as const;

export type Environment = (typeof ENVIRONMENTS)[number];

export interface Env {
  /** Which environment this instance is running in. */
  readonly environment: Environment;
  /** Base URL of the ProjectOne API. */
  readonly apiUrl: string;
}

function isEnvironment(value: string): value is Environment {
  return (ENVIRONMENTS as readonly string[]).includes(value);
}

/**
 * Read and validate configuration from a raw environment record.
 *
 * Exported separately from {@link env} so it is testable with arbitrary input
 * rather than only against the real `process.env`.
 *
 * @throws If any required variable is missing or malformed. The message lists
 *   every problem at once, so a misconfigured deploy is fixed in one pass
 *   instead of one variable per restart.
 */
export function parseEnv(source: Record<string, string | undefined>): Env {
  const problems: string[] = [];

  const rawEnvironment = source.NEXT_PUBLIC_PROJECTONE_ENVIRONMENT;
  if (rawEnvironment === undefined || rawEnvironment === "") {
    problems.push(
      "NEXT_PUBLIC_PROJECTONE_ENVIRONMENT is required (one of: " +
        `${ENVIRONMENTS.join(" | ")})`,
    );
  } else if (!isEnvironment(rawEnvironment)) {
    problems.push(
      `NEXT_PUBLIC_PROJECTONE_ENVIRONMENT must be one of: ${ENVIRONMENTS.join(" | ")} ` +
        `(received "${rawEnvironment}")`,
    );
  }

  const rawApiUrl = source.NEXT_PUBLIC_PROJECTONE_API_URL;
  if (rawApiUrl === undefined || rawApiUrl === "") {
    problems.push("NEXT_PUBLIC_PROJECTONE_API_URL is required (e.g. http://127.0.0.1:8000)");
  } else if (!URL.canParse(rawApiUrl)) {
    problems.push(
      `NEXT_PUBLIC_PROJECTONE_API_URL must be a valid absolute URL (received "${rawApiUrl}")`,
    );
  }

  if (problems.length > 0) {
    throw new Error(
      "ProjectOne web cannot start: environment configuration is invalid.\n" +
        problems.map((problem) => `  - ${problem}`).join("\n") +
        "\nSee apps/web/.env.example for the required variables.",
    );
  }

  return {
    // Both are non-null here: any missing or malformed value threw above.
    environment: rawEnvironment as Environment,
    apiUrl: rawApiUrl as string,
  };
}

/**
 * The validated configuration for this process.
 *
 * Next.js inlines `process.env.NEXT_PUBLIC_*` at build time, so these must be
 * referenced as full literal property accesses rather than looked up
 * dynamically — a computed lookup would be replaced with `undefined`.
 */
export const env: Env = parseEnv({
  NEXT_PUBLIC_PROJECTONE_ENVIRONMENT: process.env.NEXT_PUBLIC_PROJECTONE_ENVIRONMENT,
  NEXT_PUBLIC_PROJECTONE_API_URL: process.env.NEXT_PUBLIC_PROJECTONE_API_URL,
});
