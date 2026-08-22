import type { ReactNode } from "react";

/**
 * The title block every authenticated screen opens with.
 *
 * ## Why this exists
 *
 * Before this component, the same markup was hand-written sixteen times:
 * `<h1 className="text-2xl font-semibold tracking-tight text-text">` in five
 * pages, four error boundaries and their duplicated "No workspace yet"
 * branches. Sixteen copies is not a pattern, it is sixteen places for a
 * heading to drift — and [[CLAUDE|CLAUDE.md]] §39 treats the third repetition
 * as the signal to formalise, not the sixteenth.
 *
 * A Server Component. It renders text and nothing else.
 *
 * ## The display face
 *
 * `font-display` is applied here and only here in the shell, because this is
 * the shell's only text at `--text-2xl` or above — the boundary
 * [[ADR-003 Product Visual Language and Token Semantics]] Decision 5 draws for
 * the editorial serif. The face was loaded on every page from STEP-26 onward
 * and applied to nothing; this is its first consumer.
 *
 * The size is unchanged at `--text-2xl`. `--text-4xl` exists for editorial
 * display moments and choosing where those are is a per-screen decision that
 * belongs to the steps that own the screens, not to this foundation.
 *
 * **`font-semibold` is deliberately dropped** with the switch. Instrument
 * Serif ships one weight, 400 ([[Design System]] §5.1a), so asking for 600
 * would get a browser-synthesised fake bold — a smeared outline, not a
 * heavier cut. Hierarchy here comes from size, face and colour, which is what
 * §5.3 says it should come from anyway.
 */
export interface PageHeaderProps {
  /** The screen's name. Rendered as the page's one `h1` (§9.1 rule 7). */
  readonly title: string;
  /**
   * One sentence on what the screen is for, or a disclosure about the data it
   * is showing. Optional: a screen whose title says everything needs no gloss.
   */
  readonly description?: ReactNode;
  /**
   * Controls belonging to the page as a whole, laid out beside the title.
   *
   * Rendered after the title in the DOM so tab order follows visual order
   * (§9.1 rule 4) — the heading is not focusable, so the action is the first
   * stop inside the header either way.
   */
  readonly actions?: ReactNode;
}

export function PageHeader({ title, description, actions }: PageHeaderProps) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="flex flex-col gap-1">
        <h1 className="font-display text-2xl tracking-tight text-text">{title}</h1>

        {description !== undefined ? (
          <p className="max-w-prose text-sm text-text-muted">{description}</p>
        ) : null}
      </div>

      {actions !== undefined ? <div className="flex items-center gap-3">{actions}</div> : null}
    </div>
  );
}
