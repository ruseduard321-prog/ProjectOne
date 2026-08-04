/**
 * A labelled text input with its validation message.
 *
 * A Server Component — it renders markup and holds no state. The interactivity
 * lives in the form around it, which keeps this out of the client bundle
 * entirely (CLAUDE.md §11).
 *
 * Accessibility is the reason this is a component rather than repeated JSX.
 * Three things must stay wired together on every field, and doing it by hand
 * per-input is how one of them gets forgotten:
 *
 *  - the label's `htmlFor` matches the input's `id`, so clicking the label
 *    focuses the field and a screen reader announces it;
 *  - `aria-describedby` points at the error, so the message is announced rather
 *    than only seen;
 *  - `aria-invalid` marks the field itself, so the error is perceivable without
 *    relying on the red border alone ([[Design System]] §9).
 *
 * The border uses `--color-border-strong` rather than `--color-border`: the
 * decorative token does not clear WCAG's 3:1 non-text contrast, and an input
 * whose edge is invisible is a control some users cannot find (§6.2).
 */

export interface FormFieldProps {
  readonly id: string;
  readonly name: string;
  readonly label: string;
  /**
   * `text` and `number` were added by STEP-19 for the settings forms.
   *
   * `password` remains the type used for a provider API key even though it is
   * not a password: it is what makes the browser mask the value, keeps it out of
   * autofill history, and stops it being read over a user's shoulder or captured
   * in a screen share while they paste it.
   */
  readonly type: "email" | "password" | "text" | "number";
  readonly autoComplete: string;
  readonly error?: string;
  /** Hint rendered under the field when there is no error. */
  readonly hint?: string;
  readonly defaultValue?: string;
  readonly disabled?: boolean;
  /** Placeholder text. Never a substitute for the label, which is always shown. */
  readonly placeholder?: string;
  readonly required?: boolean;
  /** Passed through to `inputMode`, so a phone shows the right keyboard. */
  readonly inputMode?: "decimal" | "numeric";
}

export function FormField({
  id,
  name,
  label,
  type,
  autoComplete,
  error,
  hint,
  defaultValue,
  disabled,
  placeholder,
  required,
  inputMode,
}: FormFieldProps) {
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;

  // Only one of the two is ever present, so the description is unambiguous.
  const describedBy = error !== undefined ? errorId : hint !== undefined ? hintId : undefined;

  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={id} className="text-sm font-medium text-text">
        {label}
      </label>

      <input
        id={id}
        name={name}
        type={type}
        autoComplete={autoComplete}
        defaultValue={defaultValue}
        disabled={disabled}
        placeholder={placeholder}
        required={required}
        inputMode={inputMode}
        aria-invalid={error !== undefined}
        aria-describedby={describedBy}
        className={[
          "rounded-md border bg-surface px-3 py-2 text-base text-text",
          "placeholder:text-text-muted disabled:opacity-60",
          error !== undefined ? "border-danger" : "border-border-strong",
        ].join(" ")}
      />

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
