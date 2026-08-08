import { ASSET_KINDS, assetKindLabel } from "@/lib/projects";

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
 * A Server Component: the enclosing form owns the interactivity.
 */
export interface AssetKindFieldProps {
  readonly id: string;
  readonly name: string;
  readonly label: string;
  readonly hint?: string;
  readonly error?: string;
  readonly disabled?: boolean;
}

export function AssetKindField({
  id,
  name,
  label,
  hint,
  error,
  disabled,
}: AssetKindFieldProps) {
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
