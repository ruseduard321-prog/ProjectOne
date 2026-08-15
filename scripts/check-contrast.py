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


# --------------------------------------------------------------------------- #
# Layer 1 — primitives (Design System §6.1). No component may reference these.
# --------------------------------------------------------------------------- #

PRIMITIVES: dict[str, str] = {
    # Ivory — the warm canvas. Not grey: a cream cast is what separates this
    # from every default admin panel, and it is the direction's load-bearing hue.
    "ivory-50": "#FFFDF8",
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
    "surface": "ivory-50",
    "surface-raised": "white",
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
    "nav-surface": "ink-950",
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


def check_stylesheet_agreement() -> list[str]:
    """This script duplicates the palette deliberately; this keeps it honest."""
    actual = stylesheet_primitives()
    if not actual:
        return [f"stylesheet not found or contains no primitives: {STYLESHEET}"]

    problems: list[str] = []
    for name, expected in PRIMITIVES.items():
        if name not in actual:
            problems.append(f"primitive --{name} is missing from globals.css")
        elif actual[name] != expected.upper():
            problems.append(f"primitive --{name}: script says {expected}, globals.css says {actual[name]}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--table", action="store_true", help="print every pairing, tightest first")
    args = parser.parse_args()

    drift = check_stylesheet_agreement()
    pairings = all_pairings()
    failures = [p for p in pairings if not p.passed]
    pairings.sort(key=lambda p: p.ratio / p.bar)

    if args.table:
        print(f"{'theme':6} {'foreground':22} {'on surface':22} {'ratio':>7}  {'bar':>5}  rule")
        print("-" * 88)
        for p in pairings:
            mark = " " if p.passed else "!"
            print(f"{mark}{p.theme:5} {p.fg:22} {p.bg:22} {p.ratio:7.2f}  {p.bar:5.1f}  {p.rule}")
        print()

    if drift:
        print("PALETTE DRIFT — this script and globals.css disagree:", file=sys.stderr)
        for problem in drift:
            print(f"  {problem}", file=sys.stderr)
        print(file=sys.stderr)

    if failures:
        print(f"CONTRAST FAILURES: {len(failures)} of {len(pairings)} pairings", file=sys.stderr)
        for p in failures:
            print(
                f"  {p.theme:5} {p.fg} on {p.bg}: {p.ratio:.2f} (needs {p.bar:.1f}, {p.rule})",
                file=sys.stderr,
            )

    if drift or failures:
        return 1

    tightest = pairings[0]
    print(f"Contrast OK — {len(pairings)} pairings verified across {len(THEMES)} themes.")
    print(
        f"Tightest margin: {tightest.theme} {tightest.fg} on {tightest.bg} "
        f"= {tightest.ratio:.2f} (bar {tightest.bar:.1f})."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
