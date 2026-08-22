#!/usr/bin/env python3
"""Verify every Design System colour pairing against WCAG 2.1 AA.

[[Design System]] §6.3 states the rule this script enforces: *contrast is a
constraint on the palette, not a review step*, and *any future token change must
be re-checked the same way*. That instruction previously depended on someone
remembering it. Twice it was not remembered, and both times the result was a
shipped failure:

  - The first check (STEP-14) verified against `--color-background` and
    `--color-surface` only, omitting `--color-surface-raised`. Two dark-mode
    pairings were live failures as a result.
  - A loading skeleton was built against `--color-surface-raised`, which in
    light mode is white on a near-white canvas — a ratio of 1.05, invisible.

The lesson §6.3 draws from both is the design of this script: **a pairing that
is not checked is not passing; it is unknown.** So it enumerates every
foreground against every surface that foreground can appear on, in both themes,
rather than a hand-picked list. It runs in CI, so a token change that breaks a
pairing fails the build instead of reaching review.

The values below mirror `apps/web/src/app/globals.css`. They are duplicated
deliberately rather than parsed out of it: this script is the independent check,
and a checker that derives its expectations from the artefact it is checking
verifies only that a file equals itself. `test_matches_stylesheet` guards the
duplication by asserting the two agree.

Usage:
    python scripts/check-contrast.py            # verify, exit 1 on any failure
    python scripts/check-contrast.py --table    # also print every pairing
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# --------------------------------------------------------------------------- #
# WCAG 2.1 relative luminance and contrast ratio.
# https://www.w3.org/TR/WCAG21/#dfn-relative-luminance
# --------------------------------------------------------------------------- #


def _linearize(channel: int) -> float:
    c = channel / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _linearize(r) + 0.7152 * _linearize(g) + 0.0722 * _linearize(b)


def contrast(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def composite(fg_hex: str, alpha: float, bg_hex: str) -> str:
    """Alpha-composite `fg` at `alpha` over an opaque `bg`, the way a browser does.

    Used for the modal scrim, which is the one role whose whole job is to change
    a colour it does not replace. Compositing happens on the sRGB values, which
    is what the browser does for a translucent `background-color`.
    """
    fg, bg = fg_hex.lstrip("#"), bg_hex.lstrip("#")
    out = []
    for i in (0, 2, 4):
        f, b = int(fg[i : i + 2], 16), int(bg[i : i + 2], 16)
        out.append(round(alpha * f + (1 - alpha) * b))
    return "#" + "".join(f"{c:02X}" for c in out)


# --------------------------------------------------------------------------- #
# Layer 1 — primitives (Design System §6.1). No component may reference these.
# --------------------------------------------------------------------------- #

PRIMITIVES: dict[str, str] = {
    # Ivory — the warm canvas. Not grey: a cream cast is what separates this
    # from every default admin panel, and it is the direction's load-bearing hue.
    "ivory-50": "#FFFDF8",
    # ivory-75 keeps the light ladder warm all the way up. The ladder used to
    # end on #ffffff, which the approved direction does not contain, and which
    # left a raised surface two values from its background (ADR-007 Decision 5).
    "ivory-75": "#FDFAF3",
    "ivory-100": "#FAF6EE",
    "ivory-200": "#F2ECE1",
    "ivory-300": "#E4DBCB",
    "ivory-400": "#CFC4B0",
    # Ink — warm near-blacks and greys. Pure black is deliberately absent.
    "ink-400": "#9A9189",
    # ink-450 exists because one value could not serve both the navigation's
    # muted text (4.5 on a dark plane) and an interactive boundary on ivory
    # (3:1). See ADR-003 §2.
    "ink-450": "#8F867E",
    "ink-500": "#6E665F",
    "ink-600": "#57504A",
    "ink-700": "#3A3531",
    "ink-800": "#232120",
    "ink-900": "#121110",
    "ink-950": "#0F0E0D",
    # The deepest plane. Still not pure black, which §6.1 keeps deliberately
    # absent (ADR-007 Decision 5, superseding one row of ADR-003 Decision 2).
    "ink-975": "#070605",
    # Charcoal — dark-theme surfaces, warmer than the ink ramp so the dark
    # theme reads as the same product rather than a different one.
    "char-800": "#1A1816",
    "char-700": "#242120",
    "char-600": "#332F2C",
    # Vermilion — the single accent.
    "verm-300": "#F58555",
    "verm-400": "#F0663A",
    "verm-500": "#E2511F",
    "verm-600": "#C84016",
    "verm-700": "#A83512",
    # Semantic hues, muted toward the warm palette rather than pure spectrum.
    "green-400": "#5FA971",
    "green-600": "#2F6B3D",
    "amber-400": "#D9A339",
    "amber-700": "#7A5A0C",
    "red-400": "#EF7A68",
    "red-600": "#C0341F",
    "white": "#FFFFFF",
}

# --------------------------------------------------------------------------- #
# Layer 2 — semantic tokens (Design System §6.2). The only layer components
# may reference. Rebranding is a change to the right-hand side and nothing else.
# --------------------------------------------------------------------------- #

LIGHT: dict[str, str] = {
    "background": "ivory-100",
    "surface": "ivory-75",
    "surface-raised": "ivory-50",
    "nav-surface": "ink-900",
    "nav-surface-raised": "ink-800",
    "border": "ivory-300",
    "border-strong": "ink-450",
    "text": "ink-900",
    "text-muted": "ink-500",
    "text-on-nav": "ivory-100",
    "text-on-nav-muted": "ink-400",
    "accent": "verm-600",
    "accent-hover": "verm-700",
    "accent-fill": "verm-600",
    "accent-contrast": "white",
    "accent-on-nav": "verm-400",
    "success": "green-600",
    "warning": "amber-700",
    "danger": "red-600",
    "danger-contrast": "white",
    "skeleton": "ivory-300",
    "focus-ring": "verm-600",
}

DARK: dict[str, str] = {
    "background": "ink-950",
    "surface": "char-800",
    "surface-raised": "char-700",
    "nav-surface": "ink-975",
    "nav-surface-raised": "char-800",
    "border": "char-600",
    "border-strong": "ink-400",
    "text": "ivory-200",
    "text-muted": "ink-400",
    "text-on-nav": "ivory-200",
    "text-on-nav-muted": "ink-400",
    # One step lighter than light mode: a hue tuned against ivory is too dark
    # against near-black (Design System §6.2).
    "accent": "verm-400",
    "accent-hover": "verm-300",
    "accent-fill": "verm-500",
    "accent-contrast": "ink-950",
    "accent-on-nav": "verm-400",
    "success": "green-400",
    "warning": "amber-400",
    "danger": "red-400",
    "danger-contrast": "ink-950",
    "skeleton": "char-600",
    "focus-ring": "verm-400",
}

THEMES = {"light": LIGHT, "dark": DARK}

# --------------------------------------------------------------------------- #
# What must be checked against what.
# --------------------------------------------------------------------------- #

AA_TEXT = 4.5  # WCAG 1.4.3, body text
AA_NON_TEXT = 3.0  # WCAG 1.4.11, interactive boundaries and meaningful graphics

# A skeleton is informational, not operable: it says "content is coming". It is
# therefore not subject to the 3:1 non-text bar — but it must be *visible*, which
# is the defect that created `--color-skeleton`. This floor is a ProjectOne rule,
# not a WCAG one, and is labelled as such in the output.
SKELETON_VISIBLE = 1.2

CANVAS_SURFACES = ("background", "surface", "surface-raised")
NAV_SURFACES = ("nav-surface", "nav-surface-raised")

# Foregrounds appearing as text on the canvas.
CANVAS_TEXT = ("text", "text-muted", "accent", "accent-hover", "success", "warning", "danger")
# Foregrounds appearing as a boundary or meaningful fill on the canvas.
CANVAS_NON_TEXT = ("border-strong", "accent-fill", "focus-ring")
# Foregrounds appearing as text on the navigation plane.
NAV_TEXT = ("text-on-nav", "text-on-nav-muted", "accent-on-nav")
NAV_NON_TEXT = ("accent-on-nav", "border-strong")
# Text rendered on top of a coloured fill. `*-contrast` tokens exist so no
# component ever guesses which foreground survives on a coloured background.
ON_FILL = (("accent-contrast", "accent-fill"), ("danger-contrast", "danger"))

# --------------------------------------------------------------------------- #
# The overlay role (Design System §6.2a) — measured, but NOT a pairing.
#
# `--color-overlay` is the modal scrim. It is deliberately absent from the
# enumeration below, and the reason is a real distinction rather than an
# omission: a pairing asks "is this foreground legible on that background", and
# nothing is ever rendered ON the scrim. Both consumers paint their own panel
# above it. So it has no foreground and no contrast bar.
#
# What it does have is a property that can be got wrong, and was: POLARITY. The
# previous implementation reached for `text`, which is ivory in dark mode, so
# the scrim lightened the page it existed to subdue. That is measurable, so it
# is measured here rather than left to visual review.
# --------------------------------------------------------------------------- #

# Role -> (primitive, alpha). Mirrors globals.css; `check_overlay` guards it.
OVERLAYS: dict[str, tuple[str, float]] = {
    "light": ("ink-950", 0.45),
    "dark": ("ink-975", 0.65),
}

# Every surface the scrim is drawn over — the canvas AND the desktop rail,
# which sits behind a confirm dialog at wide viewports.
VEILED_SURFACES = CANVAS_SURFACES + NAV_SURFACES


class Pairing:
    __slots__ = ("theme", "fg", "bg", "ratio", "bar", "rule")

    def __init__(self, theme: str, fg: str, bg: str, ratio: float, bar: float, rule: str):
        self.theme, self.fg, self.bg = theme, fg, bg
        self.ratio, self.bar, self.rule = ratio, bar, rule

    @property
    def passed(self) -> bool:
        return self.ratio >= self.bar


def resolve(theme: dict[str, str], token: str) -> str:
    """Semantic token -> primitive -> hex. Fails loudly on a typo."""
    primitive = theme[token]
    return PRIMITIVES[primitive]


def all_pairings() -> list[Pairing]:
    pairings: list[Pairing] = []

    for theme_name, theme in THEMES.items():

        def add(fg: str, bg: str, bar: float, rule: str) -> None:
            pairings.append(
                Pairing(theme_name, fg, bg, contrast(resolve(theme, fg), resolve(theme, bg)), bar, rule)
            )

        for fg in CANVAS_TEXT:
            for bg in CANVAS_SURFACES:
                add(fg, bg, AA_TEXT, "AA text")

        for fg in CANVAS_NON_TEXT:
            for bg in CANVAS_SURFACES:
                add(fg, bg, AA_NON_TEXT, "AA non-text")

        # Navigation is its own surface family: a dark plane inside the light
        # theme, which the canvas tokens cannot describe (ADR-003 §3).
        for fg in NAV_TEXT:
            for bg in NAV_SURFACES:
                add(fg, bg, AA_TEXT, "AA text")

        for fg in NAV_NON_TEXT:
            for bg in NAV_SURFACES:
                add(fg, bg, AA_NON_TEXT, "AA non-text")

        for bg in CANVAS_SURFACES:
            add("skeleton", bg, SKELETON_VISIBLE, "visible (ProjectOne)")

        for fg, fill in ON_FILL:
            add(fg, fill, AA_TEXT, "AA text on fill")

    return pairings


# --------------------------------------------------------------------------- #
# Guard: the values above must match the stylesheet they describe.
# --------------------------------------------------------------------------- #

STYLESHEET = Path(__file__).resolve().parent.parent / "apps" / "web" / "src" / "app" / "globals.css"


def stylesheet_primitives() -> dict[str, str]:
    """Parse `--name: #hex;` declarations out of the primitives block."""
    if not STYLESHEET.is_file():
        return {}
    css = STYLESHEET.read_text(encoding="utf-8")
    found: dict[str, str] = {}
    for name, value in re.findall(r"--([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})\s*;", css):
        found[name] = value.upper()
    return found


def stylesheet_semantics(sentinel: str) -> dict[str, str]:
    """Parse one theme block's `--color-role: var(--primitive);` assignments.

    Blocks are located by a sentinel comment (`/* theme-block: light */`)
    rather than by their selector text. A selector is prose that gets
    reformatted; a sentinel is a marker whose only job is to be found, so
    rewrapping a comment or changing a guard cannot silently make this parser
    match nothing and check nothing.

    Args:
        sentinel: The block's marker, e.g. `theme-block: dark-attribute`.

    Returns:
        Role name (without the `--color-` prefix) to primitive name. Empty when
        the block is absent, which the caller reports as drift rather than
        treating as "nothing to check".
    """
    if not STYLESHEET.is_file():
        return {}
    css = STYLESHEET.read_text(encoding="utf-8")
    marker = css.find(f"/* {sentinel} */")
    if marker == -1:
        return {}
    start = css.rfind("{", 0, marker)
    if start == -1:
        return {}

    # Balance braces from the block's own `{` so a nested rule cannot end it
    # early. No theme block nests today; relying on that would be a parser that
    # works until the first time it does not.
    depth = 0
    for index in range(start, len(css)):
        if css[index] == "{":
            depth += 1
        elif css[index] == "}":
            depth -= 1
            if depth == 0:
                break

    body = css[start:index]
    return {
        role: primitive
        for role, primitive in re.findall(r"--color-([a-z0-9-]+):\s*var\(--([a-z0-9-]+)\)\s*;", body)
    }


def stylesheet_overlay(sentinel: str) -> tuple[str, float] | None:
    """Parse `--color-overlay: color-mix(in srgb, var(--primitive) N%, transparent);`.

    A separate parser from `stylesheet_semantics` because the overlay is the one
    semantic role whose value is not a bare `var()`: the alpha belongs IN the
    token, so that two dialogs cannot drift apart by each choosing their own.
    """
    if not STYLESHEET.is_file():
        return None
    css = STYLESHEET.read_text(encoding="utf-8")
    marker = css.find(f"/* {sentinel} */")
    if marker == -1:
        return None
    match = re.search(
        r"--color-overlay:\s*color-mix\(in srgb,\s*var\(--([a-z0-9-]+)\)\s*(\d+)%,\s*transparent\)\s*;",
        css[marker:],
    )
    return (match.group(1), int(match.group(2)) / 100) if match else None


def check_overlay() -> list[str]:
    """The scrim must DARKEN the page, in both themes.

    This is the R5 defect written as a measurement. The scrim used to be
    `text/40`, and `text` is ivory in dark mode — so opening a dialog on a dark
    page lightened it. The check composites the declared scrim over every
    surface it can be drawn over and requires the result to be no lighter than
    what it covers, and strictly darker on the canvas.

    The one permitted equality is dark `nav-surface`: the rail is already
    `ink-975`, which is the deepest value the palette contains and the scrim's
    own colour, so the veil cannot take it further down. Nothing is lightened,
    and the rail's CONTENT still dims — which is what a receding plane needs.
    """
    problems: list[str] = []

    for theme_name, sentinel in (("light", "theme-block: light"), ("dark", "theme-block: dark-attribute")):
        declared = stylesheet_overlay(sentinel)
        expected = OVERLAYS[theme_name]

        if declared is None:
            problems.append(
                f"globals.css declares no --color-overlay in the {theme_name} block, so the modal "
                "scrim is unthemed or was reverted to a per-component colour"
            )
            continue
        if declared != expected:
            problems.append(
                f"{theme_name} --color-overlay: script says {expected[0]} at {expected[1]:.0%}, "
                f"globals.css says {declared[0]} at {declared[1]:.0%}"
            )

        # Measured against what SHIPS, not against the table above. The table is
        # the mirror guard (drift is reported just above); the bar — a scrim
        # darkens — is a property of the declared value, so that is what gets
        # composited. Otherwise a reverted stylesheet would be reported as one
        # line of drift and its polarity never actually measured.
        primitive, alpha = declared
        if primitive not in PRIMITIVES:
            problems.append(f"{theme_name} scrim is mixed from --{primitive}, which is not a known primitive")
            continue
        if not 0 < alpha < 1:
            problems.append(f"{theme_name} scrim alpha {alpha} is not translucent; the page beneath must stay visible")

        scrim = PRIMITIVES[primitive]
        theme = THEMES[theme_name]
        for surface in VEILED_SURFACES:
            beneath = resolve(theme, surface)
            veiled = composite(scrim, alpha, beneath)
            before, after = luminance(beneath), luminance(veiled)

            if after > before:
                problems.append(
                    f"{theme_name} scrim LIGHTENS {surface}: {beneath} -> {veiled} "
                    f"(luminance {before:.4f} -> {after:.4f}); a veil that lightens is not a veil"
                )
            elif after == before and surface in CANVAS_SURFACES:
                problems.append(
                    f"{theme_name} scrim leaves {surface} unchanged: {beneath}; the canvas must visibly recede"
                )

    return problems


def all_color_roles(sentinel: str) -> list[str]:
    """Every `--color-*` role a block declares, whatever form its value takes."""
    if not STYLESHEET.is_file():
        return []
    css = STYLESHEET.read_text(encoding="utf-8")
    marker = css.find(f"/* {sentinel} */")
    if marker == -1:
        return []
    start = css.rfind("{", 0, marker)
    depth = 0
    for index in range(start, len(css)):
        if css[index] == "{":
            depth += 1
        elif css[index] == "}":
            depth -= 1
            if depth == 0:
                break
    return re.findall(r"--color-([a-z0-9-]+):", css[start:index])


# Roles measured somewhere other than the pairing enumeration, with the name of
# what measures them. A role here is not unchecked; it is checked differently.
NOT_A_PAIRING = {"overlay"}  # -> check_overlay(), polarity rather than contrast


def check_stylesheet_agreement() -> list[str]:
    """This script duplicates the palette deliberately; this keeps it honest.

    Three drifts are caught, and the second and third were once possible:

      1. A primitive the script names that the stylesheet does not define.
      2. A primitive the STYLESHEET defines that the script does not know.
         Previously undetected, so a new primitive could enter `globals.css`
         and never be measured against anything.
      3. A semantic role whose mapping differs between the two — including a
         role present in one and absent from the other. Previously undetected
         entirely, which meant a role added to the stylesheet was silently
         never contrast-checked. That is exactly the failure this script's
         docstring exists to prevent, one layer up from where it was guarded.
    """
    actual = stylesheet_primitives()
    if not actual:
        return [f"stylesheet not found or contains no primitives: {STYLESHEET}"]

    problems: list[str] = []
    for name, expected in PRIMITIVES.items():
        if name not in actual:
            problems.append(f"primitive --{name} is missing from globals.css")
        elif actual[name] != expected.upper():
            problems.append(f"primitive --{name}: script says {expected}, globals.css says {actual[name]}")

    for name in sorted(set(actual) - set(PRIMITIVES)):
        problems.append(
            f"primitive --{name} is defined in globals.css but unknown to this script, "
            "so nothing it is mapped to has been measured"
        )

    for theme_name, sentinel, expected_map in (
        ("light", "theme-block: light", LIGHT),
        ("dark", "theme-block: dark-attribute", DARK),
    ):
        declared = stylesheet_semantics(sentinel)
        if not declared:
            problems.append(
                f"globals.css has no `/* {sentinel} */` block, so the {theme_name} theme's "
                "semantic mapping was never compared against this script"
            )
            continue
        for role, primitive in sorted(declared.items()):
            if role not in expected_map:
                problems.append(
                    f"{theme_name} --color-{role} is declared in globals.css but absent from this "
                    "script, so it is never contrast-checked"
                )
            elif expected_map[role] != primitive:
                problems.append(
                    f"{theme_name} --color-{role}: script says {expected_map[role]}, "
                    f"globals.css says {primitive}"
                )
        for role in sorted(set(expected_map) - set(declared)):
            problems.append(f"{theme_name} --color-{role} is checked here but absent from globals.css")

        # Drift 4: a role declared in a form this script does not parse. Every
        # role above maps to a bare `var(--primitive)`; `overlay` deliberately
        # does not, and is measured by `check_overlay` instead. Anything else
        # in a third form would slip past BOTH, which is the silent skip this
        # script exists to make impossible.
        for role in sorted(set(all_color_roles(sentinel)) - set(declared) - NOT_A_PAIRING):
            problems.append(
                f"{theme_name} --color-{role} is declared in globals.css in a form this script does "
                "not parse, so it is measured by nothing"
            )

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--table", action="store_true", help="print every pairing, tightest first")
    args = parser.parse_args()

    drift = check_stylesheet_agreement()
    overlay_problems = check_overlay()
    pairings = all_pairings()
    failures = [p for p in pairings if not p.passed]
    pairings.sort(key=lambda p: p.ratio / p.bar)

    if args.table:
        print(f"{'theme':6} {'foreground':22} {'on surface':22} {'ratio':>7}  {'bar':>5}  rule")
        print("-" * 88)
        for p in pairings:
            mark = " " if p.passed else "!"
            print(f"{mark}{p.theme:5} {p.fg:22} {p.bg:22} {p.ratio:7.2f}  {p.bar:5.1f}  {p.rule}")
        print(f"{'theme':6} {'scrim over':22} {'beneath':>9}  {'veiled':>9}  luminance")
        print("-" * 88)
        for theme_name, (primitive, alpha) in OVERLAYS.items():
            for surface in VEILED_SURFACES:
                beneath = resolve(THEMES[theme_name], surface)
                veiled = composite(PRIMITIVES[primitive], alpha, beneath)
                print(
                    f" {theme_name:5} {surface:22} {beneath:>9}  {veiled:>9}  "
                    f"{luminance(beneath):.4f} -> {luminance(veiled):.4f}"
                )
        print()

    if drift:
        print("PALETTE DRIFT — this script and globals.css disagree:", file=sys.stderr)
        for problem in drift:
            print(f"  {problem}", file=sys.stderr)
        print(file=sys.stderr)

    if overlay_problems:
        print("OVERLAY POLARITY — the modal scrim does not subdue the page:", file=sys.stderr)
        for problem in overlay_problems:
            print(f"  {problem}", file=sys.stderr)
        print(file=sys.stderr)

    if failures:
        print(f"CONTRAST FAILURES: {len(failures)} of {len(pairings)} pairings", file=sys.stderr)
        for p in failures:
            print(
                f"  {p.theme:5} {p.fg} on {p.bg}: {p.ratio:.2f} (needs {p.bar:.1f}, {p.rule})",
                file=sys.stderr,
            )

    if drift or overlay_problems or failures:
        return 1

    tightest = pairings[0]
    print(f"Contrast OK — {len(pairings)} pairings verified across {len(THEMES)} themes.")
    print(
        f"Overlay OK — the scrim darkens the canvas in {len(OVERLAYS)} themes and lightens none of "
        f"the {len(VEILED_SURFACES)} surfaces it covers."
    )
    print(
        f"Tightest margin: {tightest.theme} {tightest.fg} on {tightest.bg} "
        f"= {tightest.ratio:.2f} (bar {tightest.bar:.1f})."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
