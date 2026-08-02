import type { Metadata } from "next";

import { EmptyState } from "@/components/shell/EmptyState";

export const metadata: Metadata = {
  title: "Settings — ProjectOne",
};

/**
 * Settings route placeholder.
 *
 * The real screen is [[STEP-19 Settings and BYOK UI]]. Deliberately empty: it
 * holds no form and reads no configuration, because a settings screen that
 * appears to save something and does not is worse than one that is honestly
 * unbuilt.
 */
export default function SettingsPage() {
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold tracking-tight text-text">
        Settings
      </h1>
      <EmptyState
        title="Settings are not available yet"
        description="Workspace preferences and your own AI provider keys will be managed here."
      />
    </div>
  );
}
