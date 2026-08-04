import type { ReactNode } from "react";

/**
 * One titled section of the settings screen.
 *
 * A Server Component: it renders structure and holds no state. Defined once
 * rather than repeated per section so the heading level, spacing and border
 * treatment stay identical across Profile, Workspace, AI Providers and AI Spend
 * — four hand-written variants is how a settings page ends up looking like four
 * settings pages ([[Design System]], and CLAUDE.md's Design Rules).
 *
 * The heading is an `h2` because the page owns the `h1`. Section headings that
 * skip or repeat a level are the most common way a screen becomes unnavigable
 * with a screen reader, which lists headings to move between regions.
 */
export interface SettingsSectionProps {
  readonly title: string;
  /** One sentence on what this section controls. */
  readonly description: string;
  /** Rendered at the top right — a role badge, a status, a count. */
  readonly aside?: ReactNode;
  readonly children: ReactNode;
}

export function SettingsSection({
  title,
  description,
  aside,
  children,
}: SettingsSectionProps) {
  return (
    <section
      /*
       * Labelled by its own heading, so assistive technology announces the
       * region by name rather than as an anonymous "section".
       */
      aria-labelledby={`${title.replace(/\s+/g, "-").toLowerCase()}-heading`}
      className="flex flex-col gap-4 rounded-lg border border-border bg-surface px-6 py-5"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h2
            id={`${title.replace(/\s+/g, "-").toLowerCase()}-heading`}
            className="text-lg font-medium text-text"
          >
            {title}
          </h2>
          <p className="max-w-prose text-sm text-text-muted">{description}</p>
        </div>

        {aside}
      </div>

      {children}
    </section>
  );
}
