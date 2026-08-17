"use client";

import { useSettingsFormContext } from "@/components/settings/form-context";
import type { ApiAssetKind } from "@/lib/api";
import { ASSET_KINDS, assetKindLabel, isAssetKind } from "@/lib/projects";

/**
 * The asset kind, as a fixed choice.
 *
 * **A select rather than a text input**, because `assets.kind` is a closed
 * vocabulary enforced by a database CHECK constraint. A free-text field would
 * invite a user to type "script" and receive a validation error for a value the
 * interface itself suggested was acceptable — an interface that teaches guessing.
 *
 * A separate component rather than a `select` mode added to `FormField`: that
 * component owns a labelled *input* and its accessibility wiring, and widening
 * it to render two different controls would mean every caller reads a union of
 * props that only apply to one of them. This mirrors its wiring instead —
 * `htmlFor`/`id`, `aria-describedby`, `aria-invalid` — which is the part that
 * must not drift.
 *
 * A Client Component, for the reason `FormField` gives: it is only ever rendered
 * inside a client form, and reading its error and disabled state from that
 * form's context is what lets the *page* stay on the server.
 */
export interface AssetKindFieldProps {
  readonly id: string;
  readonly name: string;
  readonly label: string;
  readonly hint?: string;
  readonly error?: string;
  readonly disabled?: boolean;
  /**
   * Notified when the selection changes.
   *
   * Optional, and the field stays **uncontrolled** either way — the value is
   * still submitted by the form, not held in React state. This exists for one
   * caller: the upload control derives its file picker's `accept` list from the
   * chosen kind, so it has to know when that choice changes.
   *
   * A callback cannot be passed from a Server Component, which is why it is
   * optional rather than required: `[projectId]/page.tsx` renders this field
   * from the server and supplies nothing.
   */
  readonly onChange?: (kind: ApiAssetKind) => void;
}

export function AssetKindField({
  id,
  name,
  label,
  hint,
  error: errorProp,
  disabled: disabledProp,
  onChange,
}: AssetKindFieldProps) {
  // Same contract as `FormField`: read from the enclosing form, prop overrides.
  const form = useSettingsFormContext();

  const error = errorProp ?? form.state.fieldErrors[name];
  const disabled = disabledProp ?? form.pending;

  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;

  const describedBy = error !== undefined ? errorId : hint !== undefined ? hintId : undefined;

  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={id} className="text-sm font-medium text-text">
        {label}
      </label>

      <select
        id={id}
        name={name}
        disabled={disabled}
        defaultValue={ASSET_KINDS[0]}
        onChange={
          onChange === undefined
            ? undefined
            : (event) => {
                // Narrowed rather than cast: the options are rendered from
                // `ASSET_KINDS`, so this always holds — and if it ever stops
                // holding, silently doing nothing beats reporting a kind the
                // API would refuse.
                if (isAssetKind(event.target.value)) {
                  onChange(event.target.value);
                }
              }
        }
        aria-invalid={error !== undefined}
        aria-describedby={describedBy}
        className={[
          "rounded-md border bg-surface px-3 py-2 text-base text-text disabled:opacity-60",
          error !== undefined ? "border-danger" : "border-border-strong",
        ].join(" ")}
      >
        {ASSET_KINDS.map((kind) => (
          <option key={kind} value={kind}>
            {assetKindLabel(kind)}
          </option>
        ))}
      </select>

      {error !== undefined ? (
        <p id={errorId} className="text-sm text-danger">
          {error}
        </p>
      ) : hint !== undefined ? (
        <p id={hintId} className="text-sm text-text-muted">
          {hint}
        </p>
      ) : null}
    </div>
  );
}
