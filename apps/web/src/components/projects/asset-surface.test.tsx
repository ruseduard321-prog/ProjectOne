/**
 * What the asset management surface renders (STEP-29).
 *
 * ## Why `renderToStaticMarkup` and not React Testing Library
 *
 * The suite runs in a node environment with no DOM (`vitest.config.ts`), and
 * this step deliberately added no test dependency: RTL plus jsdom would be two
 * packages brought in to assert strings already reachable without them
 * ([[CLAUDE|CLAUDE.md]] §28). Adopting a DOM environment is a decision worth
 * taking on its own terms, not one to smuggle in inside a UI step.
 *
 * ## What that costs, and how the cost is paid
 *
 * Static rendering cannot drive hook state or dispatch an event, so it cannot
 * click a button or watch a dialog trap focus. Two things follow:
 *
 *  1. **The upload's four states are values, not interactions.** `AssetUpload`
 *     owns the `XMLHttpRequest`; `UploadStatus` draws the result from a prop.
 *     Every state is therefore rendered and asserted below, with no DOM — which
 *     is the reason the split exists.
 *  2. **Focus order, the focus trap and `Escape` are on the manual checklist**,
 *     verified through the rendered accessibility tree. [[Design System]] §9.2
 *     already names that as the standard for dialog work, so this is the
 *     documented route rather than a concession.
 *
 * Assertions are on rendered text, ARIA attributes and hrefs — what a user or a
 * screen reader receives — never on class names, which change with styling.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { AssetList } from "@/components/projects/AssetList";
import { AssetPreview } from "@/components/projects/AssetPreview";
import { UploadStatus } from "@/components/projects/UploadStatus";
import { ConfirmDialog } from "@/components/shell/ConfirmDialog";
import type { ApiAsset, ApiAssetKind } from "@/lib/api";
import { EMPTY_FORM_STATE, type FormState } from "@/lib/form-state";
import type { AssetUrlResult } from "@/lib/projects";

const WORKSPACE = "11111111-1111-1111-1111-111111111111";
const PROJECT = "22222222-2222-2222-2222-222222222222";

/** A locator of the shape the storage layer actually persists. */
const LOCATOR = "a1b2c3d4-e5f6-4789-abcd-ef0123456789.png";

function asset(
  id: string,
  name: string,
  kind: ApiAssetKind,
  storagePath: string | null,
): ApiAsset {
  return {
    id,
    project_id: PROJECT,
    name,
    kind,
    storage_path: storagePath,
    created_by: "33333333-3333-3333-3333-333333333333",
    created_at: "2026-08-17T10:00:00+00:00",
  };
}

/*
 * Stand-ins for the server actions the page injects.
 *
 * Declared with no parameters on purpose: nothing here calls them, and a
 * narrower signature is still assignable to the wider prop type. Naming
 * arguments only to ignore them would be five unused bindings for no reader.
 */
const noopDelete = async (): Promise<FormState> => EMPTY_FORM_STATE;

const noopMint = async (): Promise<AssetUrlResult> => ({ ok: false, error: "not called" });

/** Strip tags so assertions read against what a person sees. */
function text(html: string): string {
  return html.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ");
}

function renderList(assets: readonly ApiAsset[]): string {
  return renderToStaticMarkup(
    <AssetList
      workspaceId={WORKSPACE}
      projectId={PROJECT}
      assets={assets}
      deleteAction={noopDelete}
      mint={noopMint}
    />,
  );
}

describe("UploadStatus", () => {
  it("renders nothing before an upload is attempted", () => {
    expect(renderToStaticMarkup(<UploadStatus phase={{ kind: "idle" }} />)).toBe("");
  });

  it("renders an indeterminate bar before any byte count has arrived", () => {
    const html = renderToStaticMarkup(<UploadStatus phase={{ kind: "starting" }} />);

    expect(text(html)).toContain("Starting upload");
    // No `value` attribute is what makes a progress element indeterminate. A
    // determinate bar reading 0% would claim a total the browser has not
    // reported yet.
    expect(html).toContain("<progress");
    expect(html).not.toMatch(/<progress[^>]*value=/);
  });

  it("renders a determinate bar carrying the percentage", () => {
    const html = renderToStaticMarkup(<UploadStatus phase={{ kind: "sending", percent: 42 }} />);

    expect(html).toMatch(/<progress[^>]*value="42"/);
    expect(text(html)).toContain("42%");
  });

  it("announces a failure with role=alert and the API's own message", () => {
    const html = renderToStaticMarkup(
      <UploadStatus
        phase={{
          kind: "failed",
          message: "That file type is not supported for this kind of asset.",
          requestId: "req-7",
        }}
      />,
    );

    expect(html).toContain('role="alert"');
    expect(text(html)).toContain("That file type is not supported for this kind of asset.");
    expect(text(html)).toContain("req-7");
  });

  it("announces success politely rather than interrupting", () => {
    const html = renderToStaticMarkup(
      <UploadStatus phase={{ kind: "done", name: "Opening titles" }} />,
    );

    expect(html).toContain('role="status"');
    expect(html).not.toContain('role="alert"');
    expect(text(html)).toContain("Uploaded Opening titles");
  });

  it("never echoes a filename it was not given", () => {
    // The API's refusals are written never to name the file, because a filename
    // is caller-controlled input. This component must not reintroduce it.
    const html = renderToStaticMarkup(
      <UploadStatus
        phase={{
          kind: "failed",
          message: "The file's contents do not match its declared type.",
          requestId: null,
        }}
      />,
    );

    expect(text(html)).not.toContain(".exe");
    expect(text(html)).not.toContain("Reference:");
  });
});

describe("AssetList", () => {
  it("renders an empty state that offers both ways to add an asset", () => {
    const html = renderList([]);

    expect(text(html)).toContain("No assets yet");
    expect(text(html)).toContain("Upload a file");
  });

  it("never renders an empty state as though it were a failure", () => {
    const html = renderList([]);

    // §10 rule 2: "no assets yet" and "we could not load your assets" are
    // different claims. This component only ever makes the first — a load
    // failure throws in the page and is answered by the error boundary.
    expect(html).not.toContain('role="alert"');
    expect(text(html).toLowerCase()).not.toContain("could not");
    expect(text(html).toLowerCase()).not.toContain("error");
  });

  it("renders one row per asset, named", () => {
    const html = renderList([
      asset("a1", "Opening titles", "video", LOCATOR),
      asset("a2", "Script draft", "document", null),
    ]);

    expect(text(html)).toContain("Opening titles");
    expect(text(html)).toContain("Script draft");
    expect(html.match(/<li/g)).toHaveLength(2);
  });
});

describe("AssetRow", () => {
  it("says plainly when an asset has no file, and offers no preview", () => {
    const html = renderList([asset("a1", "Script draft", "document", null)]);

    expect(text(html)).toContain("No file attached");
    // Not a broken preview and not an error — a legitimate state, produced by
    // the metadata-only form the API deliberately keeps.
    expect(html).not.toContain('role="alert"');
    expect(text(html)).not.toContain("Get link");
    expect(text(html)).not.toContain("Preview");
  });

  it("offers a preview only when the asset has bytes", () => {
    const html = renderList([asset("a1", "Cover art", "image", LOCATOR)]);

    expect(text(html)).toContain("Preview");
    expect(text(html)).not.toContain("No file attached");
  });

  it("names the asset in the confirmation, so a mis-click is visible", () => {
    const html = renderList([asset("a1", "Cover art", "image", LOCATOR)]);

    expect(text(html)).toContain("Remove this asset?");
    expect(text(html)).toContain("Cover art");
    expect(text(html)).toContain("cannot be undone");
  });

  it("never renders storage_path, in any row", () => {
    // The locator is opaque (ADR-004): the only thing the UI reads from it is
    // whether it is null. Rendering it would leak an internal identifier and
    // invite the next reader to parse it.
    const html = renderList([
      asset("a1", "Cover art", "image", LOCATOR),
      asset("a2", "Script draft", "document", null),
    ]);

    expect(html).not.toContain(LOCATOR);
  });

  it("puts no signed URL into server-rendered markup", () => {
    // D3: a signed URL is a fifteen-minute bearer capability, and this markup
    // may be cached. Nothing here may mint one — the preview control does it on
    // click, in the browser.
    const html = renderList([
      asset("a1", "Cover art", "image", LOCATOR),
      asset("a2", "Theme music", "audio", LOCATOR),
    ]);

    expect(html).not.toMatch(/https?:\/\//);
    expect(html).not.toContain("X-Amz-Signature");
    expect(html).not.toContain("<img");
    expect(html).not.toContain("<audio");
  });
});

describe("AssetPreview", () => {
  const kinds: ReadonlyArray<readonly [ApiAssetKind, string]> = [
    ["image", "Preview"],
    ["video", "Preview"],
    ["audio", "Preview"],
    // A document has no inline preview, so the control must not promise one.
    ["document", "Get link"],
  ];

  it.each(kinds)("labels the control for a %s asset as %s", (kind, label) => {
    const html = renderToStaticMarkup(
      <AssetPreview
        workspaceId={WORKSPACE}
        projectId={PROJECT}
        assetId="a1"
        assetName="Cover art"
        kind={kind}
        mint={noopMint}
      />,
    );

    expect(text(html)).toContain(label);
  });

  it("mints nothing while rendering", () => {
    let called = false;

    const mint = async (): Promise<AssetUrlResult> => {
      called = true;

      return { ok: false, error: "should not happen" };
    };

    renderToStaticMarkup(
      <AssetPreview
        workspaceId={WORKSPACE}
        projectId={PROJECT}
        assetId="a1"
        assetName="Cover art"
        kind="image"
        mint={mint}
      />,
    );

    expect(called).toBe(false);
  });
});

describe("ConfirmDialog", () => {
  const html = renderToStaticMarkup(
    <ConfirmDialog
      triggerLabel="Remove"
      title="Remove this asset?"
      description="“Cover art” will be removed. This cannot be undone."
    >
      <button type="submit">Remove asset</button>
    </ConfirmDialog>,
  );

  it("uses a native dialog, so the focus trap is the platform's", () => {
    expect(html).toContain("<dialog");
  });

  it("names and describes itself for assistive technology", () => {
    const labelledBy = /aria-labelledby="([^"]+)"/.exec(html);
    const describedBy = /aria-describedby="([^"]+)"/.exec(html);

    expect(labelledBy).not.toBeNull();
    expect(describedBy).not.toBeNull();

    // The referenced ids must actually exist in the markup, or the dialog is
    // announced as anonymous — §9.1 rule 8.
    expect(html).toContain(`id="${labelledBy?.[1] ?? ""}"`);
    expect(html).toContain(`id="${describedBy?.[1] ?? ""}"`);
  });

  it("focuses cancel first, so Enter never reaches the destructive control", () => {
    const cancelIndex = html.indexOf("Cancel");
    const confirmIndex = html.indexOf("Remove asset");

    expect(html).toMatch(/autofocus/i);
    expect(cancelIndex).toBeGreaterThan(-1);
    expect(cancelIndex).toBeLessThan(confirmIndex);
  });

  it("renders closed, so nothing is confirmed by a page load", () => {
    expect(html).not.toMatch(/<dialog[^>]*\sopen/);
  });
});

describe("asset surface source contract", () => {
  const dir = import.meta.dirname;

  const sources = [
    "AssetList.tsx",
    "AssetRow.tsx",
    "AssetPreview.tsx",
    "AssetUpload.tsx",
    "UploadStatus.tsx",
  ].map((name) => [name, readFileSync(join(dir, name), "utf8")] as const);

  it.each(sources)("never takes %s apart", (_name, source) => {
    /*
     * `storage_path` is opaque (ADR-004). Reading whether it is null is the
     * whole permitted use; splitting, slicing or prefixing it would rebuild a
     * storage key in the client, which is the boundary that makes a traversal
     * unconstructable in the first place.
     *
     * Asserted against the source because the mistake type-checks: `.split("/")`
     * on a string is valid TypeScript and only wrong for reasons a compiler
     * cannot see.
     */
    const uses = source.matchAll(/storage_path\s*([.[])/g);

    expect([...uses]).toHaveLength(0);
  });
});
