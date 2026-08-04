import type { ApiBudget, ApiSpendRecord } from "@/lib/api";

/**
 * A workspace's spend against its ceiling, and its recent AI calls.
 *
 * A Server Component — it renders values and holds no state.
 *
 * ## Amounts are never parsed to `number`
 *
 * They arrive as decimal strings and are displayed as decimal strings. Parsing
 * `"0.001234"` to a float and formatting it back is how a displayed cost stops
 * matching the ledger it came from, and this screen's whole purpose is to be
 * trusted about money.
 *
 * The one place a number is computed is the progress bar's width, where an
 * approximation is not only acceptable but unavoidable — a bar is pixels. The
 * figure beside it is the string.
 *
 * ## An open breaker is stated, not implied
 *
 * A budget screen showing a ceiling with room while every AI call is refused is
 * the silent failure CLAUDE.md §15a's graceful-degradation rule exists to
 * prevent. When the breaker is open the reason is shown, because "why are my
 * requests failing" is the question the user actually has.
 */

export interface SpendSummaryProps {
  readonly budgets: readonly ApiBudget[];
  readonly records: readonly ApiSpendRecord[];
}

/** Percentage of a ceiling consumed, for the bar only. Clamped to 0–100. */
function usedPercent(budget: ApiBudget): number {
  const limit = Number(budget.limit_usd);
  const spent = Number(budget.spent_usd);

  if (!Number.isFinite(limit) || limit <= 0) {
    return 0;
  }

  return Math.min(100, Math.max(0, (spent / limit) * 100));
}

function BudgetCard({ budget }: { readonly budget: ApiBudget }) {
  const percent = usedPercent(budget);
  const scope = budget.workflow_type ?? "All AI usage";

  return (
    <div className="flex flex-col gap-3 rounded-md border border-border px-4 py-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm font-medium text-text">{scope}</p>
        <p className="font-mono text-sm text-text-muted">
          ${budget.spent_usd} of ${budget.limit_usd}
        </p>
      </div>

      {/*
       * The bar is decorative — `aria-hidden` — because the same information is
       * already in the text above it, and a screen reader announcing a
       * progressbar's percentage alongside an exact dollar figure is noise, not
       * redundancy.
       */}
      <div aria-hidden="true" className="h-2 w-full overflow-hidden rounded-full bg-skeleton">
        <div
          className={percent >= 100 ? "h-full bg-danger" : "h-full bg-accent"}
          style={{ width: `${percent}%` }}
        />
      </div>

      <p className="text-sm text-text-muted">
        ${budget.remaining_usd} remaining · resets every {budget.period_days}{" "}
        {budget.period_days === 1 ? "day" : "days"}
      </p>

      {budget.breaker_open ? (
        <p role="status" className="rounded-md border border-danger px-3 py-2 text-sm text-danger">
          AI spending is paused for this workspace pending review.
          {budget.breaker_reason != null ? ` ${budget.breaker_reason}.` : ""} Contact an
          administrator to resume it.
        </p>
      ) : null}
    </div>
  );
}

export function SpendSummary({ budgets, records }: SpendSummaryProps) {
  return (
    <div className="flex flex-col gap-5">
      {budgets.length === 0 ? (
        <p className="text-sm text-text-muted">
          No spending limit is set. AI calls are not capped by a budget until one is.
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          {budgets.map((budget) => (
            <BudgetCard key={budget.id} budget={budget} />
          ))}
        </div>
      )}

      <div className="flex flex-col gap-2">
        <h3 className="text-sm font-medium text-text">Recent activity</h3>

        {records.length === 0 ? (
          <p className="text-sm text-text-muted">
            No AI calls yet. Usage appears here as soon as this workspace makes one.
          </p>
        ) : (
          /*
           * A real table, because this is tabular data: a screen reader user can
           * then navigate by column and hear each cell with its header, which a
           * grid of divs does not give them.
           *
           * Horizontally scrollable rather than wrapping — a cost column that
           * wraps mid-figure is unreadable on a phone.
           */
          <div className="overflow-x-auto">
            <table className="w-full min-w-md text-left text-sm">
              <caption className="sr-only">Recent AI calls, newest first</caption>
              <thead>
                <tr className="border-b border-border text-text-muted">
                  <th scope="col" className="py-2 pr-4 font-medium">
                    When
                  </th>
                  <th scope="col" className="py-2 pr-4 font-medium">
                    Model
                  </th>
                  <th scope="col" className="py-2 pr-4 font-medium">
                    Tokens
                  </th>
                  <th scope="col" className="py-2 font-medium">
                    Cost
                  </th>
                </tr>
              </thead>
              <tbody>
                {records.map((record) => (
                  <tr
                    key={`${record.created_at}-${record.model}`}
                    className="border-b border-border last:border-0"
                  >
                    <td className="py-2 pr-4 text-text-muted">
                      {/*
                       * Rendered as the ISO date the API returned rather than
                       * localised: formatting a timestamp on the server uses the
                       * server's locale and timezone, which is not the user's,
                       * and doing it on the client would make this a Client
                       * Component for a date. Localised timestamps are a real
                       * improvement and belong in the UI Polish phase.
                       */}
                      {record.created_at.slice(0, 16).replace("T", " ")}
                    </td>
                    <td className="py-2 pr-4 text-text">{record.model}</td>
                    <td className="py-2 pr-4 text-text-muted">
                      {record.prompt_tokens + record.completion_tokens}
                    </td>
                    <td className="py-2 font-mono text-text">${record.cost_usd}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
