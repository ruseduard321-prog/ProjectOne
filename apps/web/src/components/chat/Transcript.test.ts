/**
 * What the transcript shows for a question that has no reply (STEP-23).
 *
 * The defect these cover was invisible to every existing test. `turn_status` was
 * stored from the first migration, carried by the repository, and never rendered
 * — so a question whose provider call failed looked exactly like an answered one.
 * Manual testing found three of them stranded in a single conversation, each
 * `pending`, none reachable by anything on the screen.
 *
 * `turnDisplay` is asserted directly rather than through a rendered component:
 * this suite runs in a node environment with no DOM, which `vitest.config.ts`
 * justifies, and the branching is the part that was wrong. A component test
 * would need React Testing Library — a dependency this step does not need to
 * add to assert the decision that failed (CLAUDE.md §28).
 */

import { describe, expect, it } from "vitest";

import { turnDisplay } from "@/components/chat/Transcript";
import type { ApiChatMessage, ApiTurnStatus } from "@/lib/api";

/** A stored message as the API returns it. */
function message(
  role: "user" | "assistant",
  turnStatus: ApiTurnStatus | null,
): ApiChatMessage {
  return {
    id: "44444444-4444-4444-4444-444444444444",
    conversation_id: "11111111-1111-1111-1111-111111111111",
    role,
    content: role === "user" ? "Hello" : "Hello back",
    provider: role === "assistant" ? "openai" : null,
    model: role === "assistant" ? "gpt-4o-mini" : null,
    token_count: role === "assistant" ? 42 : 0,
    created_at: "2026-08-11T10:00:00+00:00",
    turn_status: turnStatus,
  };
}

describe("a question with no reply says so", () => {
  it("marks a pending question unanswered and offers Retry", () => {
    // The state a provider failure leaves behind. Both flags matter: one makes
    // the failure visible, the other makes it recoverable.
    expect(turnDisplay(message("user", "pending"))).toEqual({
      isUnanswered: true,
      isRetryable: true,
    });
  });

  it("marks an in-progress question unanswered but refuses Retry", () => {
    // In flight, or abandoned by a dead process — indistinguishable without a
    // lease, which STEP-23 excludes on purpose. Retrying could pay twice for
    // one question, so the state is surfaced and the button is not offered.
    expect(turnDisplay(message("user", "in_progress"))).toEqual({
      isUnanswered: true,
      isRetryable: false,
    });
  });
});

describe("an answered question is left alone", () => {
  it("shows nothing extra on a completed question", () => {
    // Requirement 9: a completed turn must not show Retry. Annotating the
    // ordinary case would bury the exceptional one.
    expect(turnDisplay(message("user", "completed"))).toEqual({
      isUnanswered: false,
      isRetryable: false,
    });
  });

  it("treats a question with no status as answered, not broken", () => {
    // Rows written before the turn-state migration. The migration backfills
    // them to `completed`, but a client holding an older cached response must
    // not be told its answered questions failed.
    expect(turnDisplay(message("user", null))).toEqual({
      isUnanswered: false,
      isRetryable: false,
    });
  });
});

describe("a reply is never a turn to retry", () => {
  it.each<ApiTurnStatus | null>([null, "pending", "in_progress", "completed"])(
    "offers nothing on an assistant message carrying %s",
    (status) => {
      // An assistant message's status is null by constraint. Asserting every
      // value anyway means a future write path that set one by mistake could
      // not put a Retry button under a model's own reply.
      expect(turnDisplay(message("assistant", status))).toEqual({
        isUnanswered: false,
        isRetryable: false,
      });
    },
  );
});
