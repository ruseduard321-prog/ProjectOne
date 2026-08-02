import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { signInAction } from "@/app/(auth)/actions";
import { CredentialsForm } from "@/components/auth/CredentialsForm";
import { currentProfile } from "@/lib/auth";
import { POST_SIGN_IN_PATH } from "@/lib/routes";

export const metadata: Metadata = {
  title: "Sign in · ProjectOne",
};

/**
 * The sign-in screen.
 *
 * A Server Component that redirects an already-signed-in visitor straight into
 * the application. Without that check, following a bookmark to `/sign-in` while
 * signed in presents a form that is confusing rather than useful.
 *
 * The session check also forces this route to render per-request rather than
 * being prerendered — correct, since its output depends on the caller's cookies.
 */
export default async function SignInPage() {
  if ((await currentProfile()) !== undefined) {
    redirect(POST_SIGN_IN_PATH);
  }

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold text-text">Sign in</h1>
        <p className="text-sm text-text-muted">Continue to your workspace.</p>
      </div>

      <CredentialsForm
        action={signInAction}
        submitLabel="Sign in"
        pendingLabel="Signing in…"
        passwordAutoComplete="current-password"
      />

      <p className="text-sm text-text-muted">
        No account?{" "}
        <Link href="/sign-up" className="font-medium text-accent hover:text-accent-hover">
          Create one
        </Link>
      </p>
    </div>
  );
}
