import type { Metadata } from "next";

import { EmptyState } from "@/components/shell/EmptyState";

export const metadata: Metadata = {
  title: "AI Chat — ProjectOne",
};

/**
 * AI Chat route placeholder.
 *
 * The real screen is [[STEP-23 AI Chat End to End]], which depends on the AI
 * router ([[STEP-17 AI Router and Provider Abstraction]]) and the cost controls
 * ([[STEP-18 AI Cost Governance Controls]]). Nothing here calls a provider.
 */
export default function ChatPage() {
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold tracking-tight text-text">
        AI Chat
      </h1>
      <EmptyState
        title="Chat is not available yet"
        description="Conversations will appear here once the AI layer and its cost controls are in place."
      />
    </div>
  );
}
