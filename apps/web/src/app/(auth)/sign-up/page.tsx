import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { signUpAction } from "@/app/(auth)/actions";
import { CredentialsForm } from "@/components/auth/CredentialsForm";
import { currentProfile } from "@/lib/auth";
import { PASSWORD_MIN_LENGTH } from "@/lib/credentials";
import { POST_SIGN_IN_PATH } from "@/lib/routes";

export const metadata: Metadata = {
  title: "Create an account · ProjectOne",
};

/**
 * The sign-up screen.
 *
 * Mirrors sign-in, including the already-signed-in redirect: a signed-in user
 * reaching this page wants their workspace, not a second account.
 */
export default async function SignUpPage() {
  if ((await currentProfile()) !== undefined) {
    redirect(POST_SIGN_IN_PATH);
  }

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold text-text">Create an account</h1>
        <p className="text-sm text-text-muted">Start using ProjectOne.</p>
      </div>

      <CredentialsForm
        action={signUpAction}
        submitLabel="Create account"
        pendingLabel="Creating account…"
        passwordAutoComplete="new-password"
        passwordHint={`At least ${PASSWORD_MIN_LENGTH} characters.`}
      />

      <p className="text-sm text-text-muted">
        Already have an account?{" "}
        <Link href="/sign-in" className="font-medium text-accent hover:text-accent-hover">
          Sign in
        </Link>
      </p>
    </div>
  );
}
