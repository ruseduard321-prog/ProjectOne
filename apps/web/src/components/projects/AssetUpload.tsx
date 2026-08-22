"use client";

/**
 * Uploads a file to a project, and says how far it has got.
 *
 * ## Why this is a Client Component, and why it is not a Server Action
 *
 * Every other write on this screen is a Server Action. This one cannot be, for
 * two independent reasons ([[STEP-29 Asset Management UI]] D1):
 *
 *  1. Next.js caps a Server Action body at 1 MB by default, against an API that
 *     accepts 100 MB.
 *  2. `useActionState` exposes pending or not-pending and nothing between, so it
 *     can render a spinner but never a percentage.
 *
 * `XMLHttpRequest` is used rather than `fetch` for the second of those:
 * `xhr.upload.onprogress` is the only place a browser reports bytes sent, and
 * `fetch` has no equivalent that is safe to depend on. The request goes to a
 * same-origin Route Handler, never to the API — the access token is in an
 * httpOnly cookie this code cannot read. See that handler for the boundary.
 *
 * ## What this component does not decide
 *
 * **Whether the file is acceptable.** The size check below refuses an oversized
 * file locally so a user does not spend a minute uploading something the server
 * will reject — a courtesy, not a control. Type, extension and the file's own
 * magic bytes are checked by `app/services/asset_content.py`, which is where the
 * rules cannot be bypassed. The `accept` attribute is a picker hint in exactly
 * the same sense (`lib/projects.ts`).
 *
 * The four required states ([[Design System]] §10) live in {@link UploadStatus},
 * which takes them as props so they can be rendered and asserted without a DOM.
 */

import { useRouter } from "next/navigation";
import { type FormEvent, useCallback, useState } from "react";

import { FormField } from "@/components/auth/FormField";
import { AssetKindField } from "@/components/projects/AssetKindField";
import { type UploadPhase, UploadStatus } from "@/components/projects/UploadStatus";
import type { ApiAssetKind } from "@/lib/api";
import {
  ASSET_KINDS,
  MAX_UPLOAD_BYTES,
  MAX_UPLOAD_LABEL,
  acceptForKind,
  assetUploadPath,
} from "@/lib/projects";

export interface AssetUploadProps {
  readonly workspaceId: string;
  readonly projectId: string;
}

/** Per-input messages this control raises before anything is sent. */
interface LocalErrors {
  readonly name?: string;
  readonly file?: string;
}

/** Read the API's error envelope out of a response body, however it arrived. */
function readEnvelope(raw: string): { detail: string; requestId: string | null } {
  try {
    const parsed: unknown = JSON.parse(raw);

    if (typeof parsed === "object" && parsed !== null && "detail" in parsed) {
      const { detail, request_id: requestId } = parsed as {
        detail: unknown;
        request_id?: unknown;
      };

      if (typeof detail === "string") {
        return {
          detail,
          requestId: typeof requestId === "string" ? requestId : null,
        };
      }
    }
  } catch {
    // A body that is not JSON means something answered that was not the API —
    // a proxy or a gateway. Fall through to the generic message rather than
    // rendering whatever HTML it sent.
  }

  return { detail: "The upload could not be completed. Try again.", requestId: null };
}

export function AssetUpload({ workspaceId, projectId }: AssetUploadProps) {
  const router = useRouter();

  const [phase, setPhase] = useState<UploadPhase>({ kind: "idle" });
  const [errors, setErrors] = useState<LocalErrors>({});
  const [kind, setKind] = useState<ApiAssetKind>(ASSET_KINDS[0]);

  const sending = phase.kind === "starting" || phase.kind === "sending";

  const submit = useCallback(
    (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();

      const form = event.currentTarget;
      const data = new FormData(form);

      const name = (data.get("name") as string | null)?.trim() ?? "";
      const file = data.get("file");

      const found: LocalErrors = {
        ...(name === "" ? { name: "Enter a name for this asset." } : {}),
        ...(!(file instanceof File) || file.size === 0
          ? { file: "Choose a file to upload." }
          : file.size > MAX_UPLOAD_BYTES
            ? { file: `That file is larger than the ${MAX_UPLOAD_LABEL} limit for one asset.` }
            : {}),
      };

      setErrors(found);

      if (found.name !== undefined || found.file !== undefined) {
        return;
      }

      // The trimmed name replaces what was typed, so a trailing space does not
      // become part of the stored name.
      data.set("name", name);

      const request = new XMLHttpRequest();

      request.open("POST", assetUploadPath(workspaceId, projectId));

      request.upload.addEventListener("progress", (progress) => {
        // `lengthComputable` is false until the browser knows the total. Until
        // then the phase stays `starting`, which renders an indeterminate bar
        // rather than a percentage of an unknown quantity.
        if (progress.lengthComputable && progress.total > 0) {
          setPhase({
            kind: "sending",
            percent: Math.round((progress.loaded / progress.total) * 100),
          });
        }
      });

      request.addEventListener("load", () => {
        if (request.status === 201) {
          setPhase({ kind: "done", name });

          /*
           * `reset()` restores the select to its own default, so the mirrored
           * state has to follow it. Without this the picker would keep
           * offering the previous kind's extensions against a select that
           * visibly reads something else — a small desync, but one that shows
           * the user a file dialog contradicting the form beside it.
           */
          form.reset();
          setKind(ASSET_KINDS[0]);
          setErrors({});

          // The handler already dropped the cached render; this re-requests it,
          // so the new asset appears in the server-rendered list rather than
          // being pushed into client state that would then be a second copy.
          router.refresh();

          return;
        }

        const envelope = readEnvelope(request.responseText);

        setPhase({ kind: "failed", message: envelope.detail, requestId: envelope.requestId });
      });

      /*
       * A transport failure, not a refusal: nothing judged this request, so
       * there is no status and no message from the API to show. Reported as the
       * outage it is rather than as a rejected file (CLAUDE.md §24).
       */
      request.addEventListener("error", () => {
        setPhase({
          kind: "failed",
          message: "The upload did not reach the service. Check your connection and try again.",
          requestId: null,
        });
      });

      request.addEventListener("abort", () => {
        setPhase({ kind: "idle" });
      });

      setPhase({ kind: "starting" });
      request.send(data);
    },
    [projectId, router, workspaceId],
  );

  const fileErrorId = "asset-file-error";
  const fileHintId = "asset-file-hint";

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-4">
      {/* `min-w-0`: a form control carries an intrinsic width, and a flex item
          that cannot shrink below it makes the row overflow (§9a rule 4). */}
      <div className="flex flex-col gap-4 sm:flex-row">
        <div className="min-w-0 flex-1">
          {/*
           * `error` and `disabled` are passed explicitly: this form is not a
           * `SettingsForm`, so there is no context for the fields to read them
           * from. Both components support exactly that case, which is why they
           * are reused here rather than reimplemented (CLAUDE.md §35).
           */}
          <FormField
            id="upload-name"
            name="name"
            label="Asset name"
            type="text"
            autoComplete="off"
            placeholder="Opening title card"
            error={errors.name}
            disabled={sending}
          />
        </div>

        <div className="min-w-0 flex-1">
          <AssetKindField
            id="upload-kind"
            name="kind"
            label="Kind"
            disabled={sending}
            onChange={setKind}
            hint="Decides what the file picker offers."
          />
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <label htmlFor="upload-file" className="text-sm font-medium text-text">
          File
        </label>

        <input
          id="upload-file"
          name="file"
          type="file"
          accept={acceptForKind(kind)}
          disabled={sending}
          aria-invalid={errors.file !== undefined}
          aria-describedby={errors.file !== undefined ? fileErrorId : fileHintId}
          className="rounded-md border border-border-strong bg-surface px-3 py-2 text-base text-text file:mr-3 file:rounded-md file:border-0 file:bg-surface-raised file:px-3 file:py-1 file:text-sm file:text-text disabled:opacity-60"
        />

        {errors.file !== undefined ? (
          <p id={fileErrorId} className="text-sm text-danger">
            {errors.file}
          </p>
        ) : (
          <p id={fileHintId} className="text-sm text-text-muted">
            Up to {MAX_UPLOAD_LABEL}. The file must match the kind you chose.
          </p>
        )}
      </div>

      <UploadStatus phase={phase} />

      <div>
        <button
          type="submit"
          disabled={sending}
          className="rounded-md bg-accent-fill px-4 py-2 text-sm font-medium text-accent-contrast transition-colors hover:bg-accent-hover disabled:opacity-60"
        >
          {sending ? "Uploading…" : "Upload file"}
        </button>
      </div>
    </form>
  );
}
