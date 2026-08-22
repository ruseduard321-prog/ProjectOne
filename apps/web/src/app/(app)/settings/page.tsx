import type { Metadata } from "next";

import { FormField } from "@/components/auth/FormField";
import { ProviderKeyForm } from "@/components/settings/ProviderKeyForm";
import { SettingsForm } from "@/components/settings/SettingsForm";
import { SettingsSection } from "@/components/settings/SettingsSection";
import { SpendSummary } from "@/components/settings/SpendSummary";
import { EmptyState } from "@/components/shell/EmptyState";
import {
  type ApiBudget,
  type ApiPermissions,
  type ApiProviderCredential,
  type ApiSpendRecord,
  listBudgets,
  listProviderCredentials,
  listSpendRecords,
  readPermissions,
} from "@/lib/api";
import { requireProfile, resolveAccessToken } from "@/lib/auth";
import { resolveWorkspace } from "@/lib/workspace";
import { PageHeader } from "@/components/shell/PageHeader";

import {
  renameWorkspaceAction,
  revokeProviderKeyAction,
  storeProviderKeyAction,
  updateBudgetAction,
  updateProfileAction,
} from "./actions";

export const metadata: Metadata = {
  title: "Settings — ProjectOne",
};

/**
 * The settings screen: Profile, Workspace, AI Providers and AI Spend.
 *
 * A **Server Component**, and everything it can keep on the server it does. The
 * only client code beneath it is the four form shells and the BYOK replace
 * toggle — every value on this page is fetched, decided and rendered server-side
 * (CLAUDE.md §11).
 *
 * That is not only a bundle-size preference here. The access token lives in an
 * httpOnly cookie the browser cannot read, so a client component could not fetch
 * any of this even if it wanted to — and a **provider key must never enter
 * client JavaScript**, which the Server Action path guarantees structurally
 * rather than by convention.
 *
 * ## Sections deliberately absent
 *
 * Billing, Notifications, Integrations, Connected Accounts and Storage are
 * specified in [[Settings]] but have no backend and no build step. A settings
 * section that appears to save something and does not is worse than one that is
 * honestly unbuilt, so they are not rendered at all rather than shown as
 * disabled placeholders. Security reduces to what exists: sign-out is in the
 * user menu, and MFA remains deferred out of STEP-10.
 *
 * ## Why every fetch is concurrent
 *
 * The four reads are independent and each is a round trip to the API. Awaiting
 * them in sequence would make the page four latencies deep for no reason
 * (CLAUDE.md §17).
 */
export default async function SettingsPage() {
  const profile = await requireProfile();

  // `requireProfile` already redirected if there were no session, so a token
  // exists here. Resolved again rather than threaded through, because the gate
  // returns a profile rather than a token and widening it for one caller would
  // be worse than one extra cookie read.
  const accessToken = await resolveAccessToken();

  const workspace = accessToken === undefined ? undefined : await resolveWorkspace(accessToken);

  if (accessToken === undefined || workspace === undefined) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader title="Settings" />
        <EmptyState
          title="No workspace yet"
          description="Workspace settings, AI provider keys and spending limits appear here once you belong to a workspace."
        />
      </div>
    );
  }

  const workspaceId = workspace.current.id;

  const [permissions, credentials, budgets, records] = await Promise.all([
    readPermissions(accessToken, workspaceId),
    listProviderCredentials(accessToken, workspaceId),
    listBudgets(accessToken, workspaceId),
    listSpendRecords(accessToken, workspaceId),
  ]);

  return (
    <SettingsScreen
      displayName={profile.display_name}
      email={profile.email}
      workspaceId={workspaceId}
      workspaceName={workspace.current.name}
      otherWorkspaceCount={workspace.available.length - 1}
      permissions={permissions}
      credentials={credentials}
      budgets={budgets}
      records={records}
    />
  );
}

/** Providers a workspace may configure, matching the API's accepted set. */
const PROVIDERS = [
  { id: "openai", label: "OpenAI" },
  { id: "anthropic", label: "Anthropic" },
] as const;

interface SettingsScreenProps {
  readonly displayName: string | null;
  readonly email: string;
  readonly workspaceId: string;
  readonly workspaceName: string;
  readonly otherWorkspaceCount: number;
  readonly permissions: ApiPermissions;
  readonly credentials: readonly ApiProviderCredential[];
  readonly budgets: readonly ApiBudget[];
  readonly records: readonly ApiSpendRecord[];
}

/**
 * The rendered screen, separated from the data fetching above it.
 *
 * Presentation and orchestration split so the layout is readable without the
 * awaits, and so a future test can render it against fixed props.
 */
function SettingsScreen({
  displayName,
  email,
  workspaceId,
  workspaceName,
  otherWorkspaceCount,
  permissions,
  credentials,
  budgets,
  records,
}: SettingsScreenProps) {
  /*
   * The client's copy of the server's rule, used only to render honestly.
   *
   * `GET /permissions` exists precisely so an interface can match what the
   * server will allow rather than offering an action and discovering the 403
   * after the user has committed to it. It is never the enforcement: every route
   * checks again regardless of what this page believes.
   */
  const mayWrite = permissions.permissions.includes("workspace:update");
  const writeRefusal = mayWrite
    ? undefined
    : `Your role in this workspace is ${permissions.role}. Only an owner or admin can change this.`;

  const lastFourFor = (provider: string): string | undefined =>
    credentials.find((credential) => credential.provider === provider)?.last_four;

  const workspaceBudget = budgets.find((budget) => budget.workflow_type === null);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Settings"
        description={
          <>
            Your profile, and the settings for {workspaceName}.
            {/*
             * The multi-workspace limitation, disclosed rather than hidden. A
             * user with several workspaces silently editing only the first would
             * be a data-integrity surprise; saying which one is being shown makes
             * it a known constraint. See `lib/workspace.ts`.
             */}
            {otherWorkspaceCount > 0
              ? ` You belong to ${otherWorkspaceCount} other ${
                  otherWorkspaceCount === 1 ? "workspace" : "workspaces"
                } — switching between them is not available yet.`
              : ""}
          </>
        }
      />

      <SettingsSection
        title="Profile"
        description="How you appear to other people in your workspaces."
      >
        <SettingsForm
          action={updateProfileAction}
          submitLabel="Save profile"
          pendingLabel="Saving…"
        >
          <div className="flex flex-col gap-4">
            <FormField
              id="profile-display-name"
              name="display_name"
              label="Display name"
              type="text"
              autoComplete="name"
              defaultValue={displayName ?? ""}
            />

            {/*
               * Email is shown as text rather than a disabled input. A disabled
               * field suggests the value is editable under some condition; it
               * is not editable here at all, because the address is
               * authoritative in the identity provider and a write would be
             * reconciled away on the next request.
             */}
            <div className="flex flex-col gap-1">
              <p className="text-sm font-medium text-text">Email</p>
              <p className="text-sm text-text-muted">{email}</p>
            </div>
          </div>
        </SettingsForm>
      </SettingsSection>

      <SettingsSection
        title="Workspace"
        description="The name everyone in this workspace sees."
        aside={
          <span className="rounded-full border border-border px-3 py-1 text-xs font-medium text-text-muted">
            You are {permissions.role === "admin" ? "an" : "the"} {permissions.role}
          </span>
        }
      >
        <SettingsForm
          action={renameWorkspaceAction}
          submitLabel="Save workspace"
          pendingLabel="Saving…"
          hidden={{ workspace_id: workspaceId }}
          disabledReason={writeRefusal}
        >
          <FormField
            id="workspace-name"
            name="name"
            label="Workspace name"
            type="text"
            autoComplete="off"
            defaultValue={workspaceName}
          />
        </SettingsForm>
      </SettingsSection>

      <SettingsSection
        title="AI Providers"
        description="Your own provider keys. Calls are billed to your provider account, and keys are encrypted before they are stored."
      >
        <div className="flex flex-col gap-3">
          {PROVIDERS.map((provider) => (
            <ProviderKeyForm
              key={provider.id}
              workspaceId={workspaceId}
              provider={provider.id}
              label={provider.label}
              lastFour={lastFourFor(provider.id)}
              disabledReason={writeRefusal}
              storeAction={storeProviderKeyAction}
              revokeAction={revokeProviderKeyAction}
            />
          ))}
        </div>
      </SettingsSection>

      <SettingsSection
        title="AI Spend"
        description="What this workspace has spent, and the ceiling it is spent against."
      >
        <div className="flex flex-col gap-6">
          <SpendSummary budgets={budgets} records={records} />

          <SettingsForm
            action={updateBudgetAction}
            submitLabel={workspaceBudget === undefined ? "Set limit" : "Update limit"}
            pendingLabel="Saving…"
            hidden={{ workspace_id: workspaceId }}
            disabledReason={writeRefusal}
          >
            <div className="flex flex-col gap-4 sm:flex-row sm:gap-4">
              <div className="flex-1">
                <FormField
                  id="budget-limit"
                  name="limit_usd"
                  label="Spending limit (USD)"
                  type="text"
                  autoComplete="off"
                  inputMode="decimal"
                  placeholder="50.00"
                  defaultValue={workspaceBudget?.limit_usd ?? ""}
                />
              </div>

              <div className="flex-1">
                <FormField
                  id="budget-period"
                  name="period_days"
                  label="Period (days)"
                  type="text"
                  autoComplete="off"
                  inputMode="numeric"
                  placeholder="30"
                  defaultValue={
                    workspaceBudget === undefined ? "" : String(workspaceBudget.period_days)
                  }
                  hint="Leave blank to keep the current period."
                />
              </div>
            </div>
          </SettingsForm>
        </div>
      </SettingsSection>
    </div>
  );
}
