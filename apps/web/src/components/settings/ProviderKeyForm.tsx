"use client";

/**
 * The BYOK entry form for one provider.
 *
 * ## Why this never renders a stored key
 *
 * Because none is retrievable. `ProviderCredentialService.key_for` is the only
 * code that produces a plaintext key, no route calls it, and the response type
 * this screen consumes has no field capable of carrying one. So "show my key"
 * is not a feature that was declined — it is one the backend structurally cannot
 * serve, and this component is built around that rather than working against it.
 *
 * What a user sees for a configured provider is `••••••••1234`: enough to
 * recognise *which* key is stored, and useless to anyone who reads it over their
 * shoulder.
 *
 * ## The replace affordance is explicit
 *
 * A key that is already stored does not put an empty input on screen. Replacing
 * a working credential is a deliberate act — an always-present input invites a
 * half-pasted value over a key that was working, and the failure surfaces later,
 * on an AI call, far from the mistake. Clicking "Replace" is the confirmation.
 *
 * A Client Component for exactly one reason: toggling that affordance. The
 * masked display and everything around it would otherwise be server-rendered.
 */

import { useState } from "react";

import { FormField } from "@/components/auth/FormField";
import { SettingsForm } from "@/components/settings/SettingsForm";
import type { FormState } from "@/lib/form-state";

export interface ProviderKeyFormProps {
  readonly workspaceId: string;
  /** Provider identifier the API accepts, e.g. `openai`. */
  readonly provider: string;
  /** Human-readable name, e.g. `OpenAI`. */
  readonly label: string;
  /** Last four characters of the stored key, or `undefined` when none is set. */
  readonly lastFour?: string;
  /** Undefined when the caller may write; a reason when they may not. */
  readonly disabledReason?: string;
  readonly storeAction: (previous: FormState, data: FormData) => Promise<FormState>;
  readonly revokeAction: (previous: FormState, data: FormData) => Promise<FormState>;
}

export function ProviderKeyForm({
  workspaceId,
  provider,
  label,
  lastFour,
  disabledReason,
  storeAction,
  revokeAction,
}: ProviderKeyFormProps) {
  const configured = lastFour !== undefined;
  const [replacing, setReplacing] = useState(false);

  const showInput = !configured || replacing;
  const hidden = { workspace_id: workspaceId, provider };

  return (
    <div className="flex flex-col gap-4 rounded-md border border-border px-4 py-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-col gap-1">
          <p className="text-sm font-medium text-text">{label}</p>

          {configured ? (
            /*
             * The mask is text rather than a password input: this is a display,
             * not a field, and a disabled input holding dots would suggest the
             * value is there to be revealed. It is not.
             */
            <p className="font-mono text-sm text-text-muted">
              {"•".repeat(8)}
              {lastFour}
            </p>
          ) : (
            <p className="text-sm text-text-muted">No key stored.</p>
          )}
        </div>

        {configured && !replacing && disabledReason === undefined ? (
          <button
            type="button"
            onClick={() => setReplacing(true)}
            className="rounded-md border border-border-strong px-3 py-1.5 text-sm text-text transition-colors hover:bg-surface-raised"
          >
            Replace
          </button>
        ) : null}
      </div>

      {showInput ? (
        <SettingsForm
          action={storeAction}
          submitLabel={configured ? "Replace key" : "Save key"}
          pendingLabel="Saving…"
          savedLabel="Key saved"
          hidden={hidden}
          disabledReason={disabledReason}
        >
          <FormField
            id={`${provider}-api-key`}
            name="api_key"
            label={`${label} API key`}
            /*
               * `password`, so the browser masks it. Not because it is a
             * password, but because everything that treatment buys — masking,
             * exclusion from autofill history, no plaintext in a screen share
             * — is exactly what a provider key needs.
             */
            type="password"
            /*
             * `off`, deliberately. Letting a password manager save a provider
             * key under this origin puts a credential somewhere the user did
             * not choose to put it, and offering to autofill it later is how
             * one workspace's key ends up pasted into another's form.
             */
            autoComplete="off"
            placeholder="sk-…"
            hint="Pasted once and encrypted. It is never shown again — replace it if you lose it."
          />
        </SettingsForm>
      ) : null}

      {configured && disabledReason === undefined ? (
        <SettingsForm
          action={revokeAction}
          submitLabel="Remove key"
          pendingLabel="Removing…"
          savedLabel="Key removed"
          hidden={hidden}
          intent="danger"
        >
          <p className="text-sm text-text-muted">
            Removing this key stops AI features that use {label}.
          </p>
        </SettingsForm>
      ) : null}
    </div>
  );
}
