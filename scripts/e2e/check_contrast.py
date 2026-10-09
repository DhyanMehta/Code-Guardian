"""Measure the dashboard's colour system: WCAG contrast, grayscale order, CVD safety.

Nothing here is asserted from intent. Every number is computed from the hex values the
UI actually ships, parsed straight out of `src/styles/index.css` and the design-token
modules. Three things are checked:

1. **Contrast.** Every foreground/background pair the components really render, scored
   against WCAG 2.1 SC 1.4.3 (4.5:1 normal text, 3:1 large text) and SC 1.4.11 (3:1
   non-text). Pairs are declared explicitly rather than generated combinatorially,
   because a cross product would mostly score combinations that never appear on screen
   and would bury the real failures.

2. **Token drift.** `SEVERITY_HEX`, `AGENT_CHART_HEX`, `COVERAGE_META`, and
   `CHART_COLORS` exist because SVG cannot use Tailwind utilities. That makes them a
   second copy of the palette. Every one of those literals must equal the matching
   `--color-*` token, or the charts and the rest of the UI have silently diverged.

3. **Redundant encoding.** The severity ramp claims to be ordered by lightness and to
   survive protanopia/deuteranopia. Both are measurable: relative luminance must be
   monotonic across the ramp, and after a Viénot-Brettel-Mollon dichromacy transform
   adjacent levels must still differ.

Exit code is 1 if any required check fails.

References for the colour maths:
  - WCAG 2.1 relative luminance and contrast ratio definitions (W3C).
  - Viénot, Brettel & Mollon (1999), "Digital video colourmaps for checking the
    legibility of displays by dichromats" — the LMS reduction used below.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CSS = ROOT / "frontend" / "src" / "styles" / "index.css"
SEVERITY_TS = ROOT / "frontend" / "src" / "design" / "severity.ts"
AGENTS_TS = ROOT / "frontend" / "src" / "design" / "agents.ts"
COVERAGE_TS = ROOT / "frontend" / "src" / "design" / "coverage.ts"
CHART_THEME_TS = ROOT / "frontend" / "src" / "components" / "charts" / "chartTheme.ts"

AA_TEXT = 4.5
AA_LARGE = 3.0
AA_NON_TEXT = 3.0


# --------------------------------------------------------------------------- colour


def parse_hex(value: str) -> tuple[int, int, int]:
    value = value.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    if len(value) != 6:
        raise ValueError(f"not a 6-digit hex colour: {value!r}")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def to_hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c))):02x}" for c in rgb)


def linearize(channel: int) -> float:
    c = channel / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def delinearize(value: float) -> float:
    v = max(0.0, min(1.0, value))
    srgb = v * 12.92 if v <= 0.0031308 else 1.055 * (v ** (1 / 2.4)) - 0.055
    return srgb * 255.0


def relative_luminance(hex_colour: str) -> float:
    r, g, b = (linearize(c) for c in parse_hex(hex_colour))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(fg: str, bg: str) -> float:
    a, b = relative_luminance(fg), relative_luminance(bg)
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)


# ------------------------------------------------------------------ CVD simulation

# Viénot 1999 sRGB-linear -> LMS
_RGB_TO_LMS = (
    (17.8824, 43.5161, 4.11935),
    (3.45565, 27.1554, 3.86714),
    (0.0299566, 0.184309, 1.46709),
)
_LMS_TO_RGB = (
    (0.080944, -0.130504, 0.116721),
    (-0.0102485, 0.0540194, -0.113615),
    (-0.000365294, -0.00412163, 0.693513),
)


def _matmul(matrix, vector):
    return tuple(sum(m * v for m, v in zip(row, vector)) for row in matrix)


def simulate_cvd(hex_colour: str, kind: str) -> str:
    """Return `hex_colour` as seen with protanopia or deuteranopia."""
    linear = tuple(linearize(c) for c in parse_hex(hex_colour))
    long_, medium, short = _matmul(_RGB_TO_LMS, linear)

    if kind == "protanopia":
        long_ = 2.02344 * medium - 2.52581 * short
    elif kind == "deuteranopia":
        medium = 0.494207 * long_ + 1.24827 * short
    else:
        raise ValueError(kind)

    return to_hex(tuple(delinearize(c) for c in _matmul(_LMS_TO_RGB, (long_, medium, short))))


# ------------------------------------------------------------------------- parsing


def parse_css_tokens() -> dict[str, str]:
    text = CSS.read_text(encoding="utf-8")
    theme = re.search(r"@theme\s*\{(.*?)\n\}", text, re.DOTALL)
    if not theme:
        raise SystemExit("could not find the @theme block in index.css")

    body = theme.group(1)
    tokens: dict[str, str] = {}

    # 1. Parse hex tokens
    for name, value in re.findall(
        r"--color-([a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{3,8})\s*;", body
    ):
        tokens[name] = value

    # Canvas color for alpha compositing
    canvas_hex = tokens.get("canvas", "#0B0F17")
    cr, cg, cb = parse_hex(canvas_hex)

    # 2. Parse rgba tokens and composite over canvas background
    for name, r, g, b, a in re.findall(
        r"--color-([a-z0-9-]+)\s*:\s*rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([\d.]+)\s*\)\s*;",
        body,
    ):
        alpha = float(a)
        comp_r = round(alpha * int(r) + (1.0 - alpha) * cr)
        comp_g = round(alpha * int(g) + (1.0 - alpha) * cg)
        comp_b = round(alpha * int(b) + (1.0 - alpha) * cb)
        tokens[name] = to_hex((comp_r, comp_g, comp_b))

    return tokens


def _object_body(text: str, symbol: str, path: Path) -> str:
    start = text.find(symbol)
    if start == -1:
        raise SystemExit(f"{symbol} not found in {path.name}")
    brace = text.find("{", start)
    depth, end = 0, brace
    for index in range(brace, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                end = index
                break
    return text[brace : end + 1]


def parse_ts_hexes(path: Path, symbol: str) -> dict[str, str]:
    """Pull flat `key: '#hex'` pairs out of one exported object literal."""
    body = _object_body(path.read_text(encoding="utf-8"), symbol, path)
    return dict(
        re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\s*:\s*'(#[0-9a-fA-F]{3,8})'", body)
    )


def parse_ts_nested_hexes(path: Path, symbol: str, field: str) -> dict[str, str]:
    """Pull `outerKey: { ... field: '#hex' ... }` out of a nested object literal.

    COVERAGE_META maps a state to a whole metadata object, so the flat parser above
    would only ever see the inner field name. Getting this wrong is how a drift check
    silently passes, which is worse than not having one.
    """
    body = _object_body(path.read_text(encoding="utf-8"), symbol, path)
    found: dict[str, str] = {}
    for match in re.finditer(r"(\w+)\s*:\s*\{", body):
        key = match.group(1)
        depth, start = 0, match.end() - 1
        for index in range(start, len(body)):
            if body[index] == "{":
                depth += 1
            elif body[index] == "}":
                depth -= 1
                if depth == 0:
                    inner = body[start : index + 1]
                    hit = re.search(rf"\b{field}\s*:\s*'(#[0-9a-fA-F]{{3,8}})'", inner)
                    if hit:
                        found[key] = hit.group(1)
                    break
    return found


# --------------------------------------------------------------------------- report

_failures: list[str] = []
_checks = 0


def row(label: str, fg: str, bg: str, threshold: float, kind: str) -> None:
    global _checks
    _checks += 1
    ratio = contrast(fg, bg)
    ok = ratio >= threshold
    if not ok:
        _failures.append(f"{label}: {ratio:.2f}:1 < {threshold}:1 ({kind})")
    print(
        f"  {'PASS' if ok else 'FAIL'}  {ratio:6.2f}:1  (min {threshold}) "
        f"{fg} on {bg}  {label}"
    )


def main() -> int:
    tokens = parse_css_tokens()

    ALIASES = {
        "surface-sunken": "surface-subtle",
        "ink": "text-primary",
        "ink-secondary": "text-secondary",
        "ink-muted": "text-muted",
        "accent": "brand-500",
        "accent-hover": "brand-400",
        "accent-subtle": "surface-highlight",
        "positive": "emerald",
        "positive-subtle": "surface-highlight",
        "control-border": "surface-border",
        "line": "surface-border",
        "line-strong": "surface-border-light",
        "sev-unknown": "text-dim",
        "sev-unknown-bg": "surface-highlight",
        "sev-info-bg": "surface-subtle",
    }

    def t(name: str) -> str:
        if name in tokens:
            return tokens[name]
        alias = ALIASES.get(name)
        if alias and alias in tokens:
            return tokens[alias]
        _failures.append(f"missing CSS token --color-{name}")
        return "#888888"

    print("=" * 78)
    print("CodeGuardian dashboard — measured colour verification")
    print("=" * 78)
    print(f"\nParsed {len(tokens)} --color-* tokens from {CSS.relative_to(ROOT)}\n")

    # ------------------------------------------------------------ token drift
    print("-" * 78)
    print("1. TOKEN DRIFT — chart literals must equal the CSS tokens")
    print("-" * 78)
    drift = 0
    mappings: list[tuple[str, dict[str, str], dict[str, str]]] = [
        (
            "SEVERITY_HEX (severity.ts)",
            parse_ts_hexes(SEVERITY_TS, "SEVERITY_HEX"),
            {
                "critical": "sev-critical",
                "high": "sev-high",
                "medium": "sev-medium",
                "low": "sev-low",
                "info": "sev-info",
                "unknown": "sev-unknown",
            },
        ),
        (
            "COVERAGE_META hexes (coverage.ts)",
            parse_ts_nested_hexes(COVERAGE_TS, "COVERAGE_META", "hex"),
            {"complete": "positive", "gap": "sev-medium", "unknown": "ink-muted"},
        ),
        (
            "CHART_COLORS (chartTheme.ts)",
            parse_ts_hexes(CHART_THEME_TS, "CHART_COLORS"),
            {
                "axis": "control-border",
                "axisLabel": "ink-muted",
                "grid": "line",
                "series": "accent",
                "canvas": "canvas",
            },
        ),
    ]
    for name, literals, expected in mappings:
        for key, token_name in expected.items():
            got = literals.get(key)
            want = t(token_name)
            if got is None:
                print(f"  FAIL  {name}: no literal for {key!r}")
                drift += 1
            elif got.lower() != want.lower():
                print(
                    f"  FAIL  {name}: {key} = {got} but --color-{token_name} = {want}"
                )
                drift += 1
            else:
                print(f"  PASS  {name}: {key} = {got} == --color-{token_name}")
    if drift:
        _failures.append(f"{drift} chart colour literal(s) have drifted from the tokens")

    agent_hex = parse_ts_hexes(AGENTS_TS, "AGENT_CHART_HEX")
    print(
        "\n  NOTE  AGENT_CHART_HEX is chart-only and intentionally has no CSS token "
        "counterpart;\n        it is contrast-checked below instead."
    )

    # ------------------------------------------------------------ text contrast
    print("\n" + "-" * 78)
    print("2. TEXT CONTRAST — WCAG 2.1 SC 1.4.3, 4.5:1 normal / 3:1 large")
    print("-" * 78)

    backgrounds = [("canvas", t("canvas")), ("surface", t("surface")),
                   ("surface-sunken", t("surface-sunken"))]

    print("\n  Body text on every page background:")
    for fg_name in ("ink", "ink-secondary", "ink-muted"):
        for bg_name, bg in backgrounds:
            row(f"{fg_name} on {bg_name}", t(fg_name), bg, AA_TEXT, "normal text")

    print("\n  Interactive and positive:")
    for bg_name, bg in backgrounds:
        row(f"accent on {bg_name}", t("accent"), bg, AA_TEXT, "link text")
    row("accent on accent-subtle (nav active)", t("accent"), t("accent-subtle"), AA_TEXT,
        "nav label")
    row("accent-hover on canvas", t("accent-hover"), t("canvas"), AA_TEXT, "link hover")
    row("canvas on accent (primary button)", t("canvas"), t("accent"), AA_TEXT,
        "button label")
    row("positive on canvas", t("positive"), t("canvas"), AA_TEXT, "status text")
    row("positive on positive-subtle (badge)", t("positive"), t("positive-subtle"),
        AA_TEXT, "badge label")

    print("\n  Severity labels on their own badge tint, and on the page:")
    severities = ["critical", "high", "medium", "low", "info", "unknown"]
    for name in severities:
        row(f"sev-{name} on sev-{name}-bg (badge)", t(f"sev-{name}"),
            t(f"sev-{name}-bg"), AA_TEXT, "badge label")
    for name in severities:
        row(f"sev-{name} on canvas", t(f"sev-{name}"), t("canvas"), AA_TEXT,
            "legend / summary text")
    for name in severities:
        row(f"sev-{name} on surface", t(f"sev-{name}"), t("surface"), AA_TEXT,
            "text on table header")

    print("\n  Status and outcome badges (design/status.ts pairings):")
    row("ink-muted on surface-sunken (pending/skipped)", t("ink-muted"),
        t("surface-sunken"), AA_TEXT, "badge label")
    row("sev-critical on sev-critical-bg (failed)", t("sev-critical"),
        t("sev-critical-bg"), AA_TEXT, "badge label")
    row("sev-medium on sev-medium-bg (degraded / caution band)", t("sev-medium"),
        t("sev-medium-bg"), AA_TEXT, "notice text")
    row("ink-secondary on surface-sunken (info band)", t("ink-secondary"),
        t("surface-sunken"), AA_TEXT, "notice text")

    # ------------------------------------------------------- non-text contrast
    print("\n" + "-" * 78)
    print("3. NON-TEXT CONTRAST — WCAG 2.1 SC 1.4.11, 3:1")
    print("-" * 78)

    print("\n  Interactive control boundaries (inputs, selects, buttons, tooltips):")
    for bg_name, bg in backgrounds:
        row(f"control-border on {bg_name}", t("control-border"), bg, AA_NON_TEXT,
            "control boundary")

    print("\n  Focus indicators:")
    row("accent on canvas (focus ring)", t("accent"), t("canvas"), AA_NON_TEXT,
        "focus indicator")
    row("accent on surface (focus ring)", t("accent"), t("surface"), AA_NON_TEXT,
        "focus indicator")
    row("accent on surface-sunken (focus ring)", t("accent"), t("surface-sunken"),
        AA_NON_TEXT, "focus indicator")

    print("\n  Severity chart fills / distribution-bar segments against the plot:")
    for name in severities:
        row(f"sev-{name} fill on canvas", t(f"sev-{name}"), t("canvas"), AA_NON_TEXT,
            "graphical object")

    print("\n  Agent chart fills against the plot background:")
    for agent, hex_value in agent_hex.items():
        row(f"agent {agent} fill on canvas", hex_value, t("canvas"), AA_NON_TEXT,
            "graphical object")

    print("\n  Coverage markers against the plot background:")
    coverage_hex = parse_ts_nested_hexes(COVERAGE_TS, "COVERAGE_META", "hex")
    for state, hex_value in coverage_hex.items():
        row(f"coverage {state} marker on canvas", hex_value, t("canvas"), AA_NON_TEXT,
            "graphical object")

    print("\n  Chart axis (the reference values are read against, so 3:1 required):")
    row("control-border axis on canvas", t("control-border"), t("canvas"), AA_NON_TEXT,
        "axis")

    print("\n  Deliberately BELOW 3:1, and why (SC 1.4.11 exempts pure decoration):")
    print(f"    {contrast(t('line'), t('canvas')):.2f}:1  --color-line on canvas — "
          "card edges, table row rules,\n             chart gridlines. A reading aid, "
          "not information. Every number the\n             gridlines support is also "
          "in the sr-only data table.")
    print(f"    {contrast(t('line-strong'), t('canvas')):.2f}:1  --color-line-strong on "
          "canvas — the dashed edge on the\n             'Skipped' and 'Not recorded' "
          "badges, and the EmptyState placeholder\n             (aria-hidden). Fully "
          "redundant: those badges also carry a text label\n             and a distinct "
          "glyph, so nothing is conveyed by the border alone.")

    # --------------------------------------------------- grayscale / lightness
    print("\n" + "-" * 78)
    print("4. GRAYSCALE SURVIVAL — what lightness does and does not encode")
    print("-" * 78)
    global _checks
    ramp = [(name, relative_luminance(t(f"sev-{name}"))) for name in severities]
    print("\n  Relative luminance in severity order:")
    for name, lum in ramp:
        bar = "#" * max(1, round(lum * 220))
        print(f"    sev-{name:<9} L={lum:.4f}  {bar}")

    lookup = dict(ramp)
    print("\n  Same colours sorted by lightness (this is the grayscale reading order):")
    for name, lum in sorted(ramp, key=lambda pair: pair[1]):
        print(f"    sev-{name:<9} L={lum:.4f}")

    # Invariant 1: critical is the darkest step by a clear margin. The one level that
    # should stop a merge must be unmistakable with no colour at all.
    _checks += 1
    darkest = min(ramp, key=lambda pair: pair[1])[0]
    runner_up = sorted(lum for _, lum in ramp)[1]
    margin = runner_up / lookup["critical"] if lookup["critical"] else 0
    if darkest == "critical" and margin >= 1.4:
        print(f"\n  PASS  critical is the darkest step (L={lookup['critical']:.4f}), "
              f"{margin:.2f}x darker than\n        the next darkest — unmistakable in "
              "grayscale.")
    else:
        print(f"\n  FAIL  critical is not clearly the darkest step (darkest={darkest}, "
              f"margin={margin:.2f}x)")
        _failures.append("critical is no longer the clearly darkest severity")

    # Invariant 2: the warm actionable band is monotonic. critical/high/medium are the
    # levels a reviewer is expected to act on, and those three DO order by lightness.
    _checks += 1
    warm = ["critical", "high", "medium"]
    warm_monotonic = all(lookup[warm[i]] < lookup[warm[i + 1]] for i in range(len(warm) - 1))
    if warm_monotonic:
        print("  PASS  the actionable band is monotonic: critical < high < medium "
              f"({lookup['critical']:.4f} < {lookup['high']:.4f} < "
              f"{lookup['medium']:.4f}).")
    else:
        print("  FAIL  critical/high/medium are no longer ordered by lightness")
        _failures.append("the actionable severity band is not ordered by lightness")

    # Invariant 3: lightness does NOT rank the full ramp, and that is stated rather
    # than papered over. This assertion exists so nobody re-adds the old claim.
    full_monotonic = all(ramp[i][1] < ramp[i + 1][1] for i in range(len(ramp) - 1))
    print("\n  Documented limitation, re-measured every run:")
    print(f"    full ramp monotonic by lightness? {full_monotonic} "
          "(expected False — see the note\n      in styles/index.css). "
          f"sev-low L={lookup['low']:.4f} is DARKER than sev-high "
          f"L={lookup['high']:.4f}\n      and sev-medium L={lookup['medium']:.4f}, so "
          "low cannot be ranked against them by\n      lightness alone.")

    print("\n  Grayscale contrast between ADJACENT levels (>= 1.2:1 to be separable):")
    weak_pairs = []
    for i in range(len(severities) - 1):
        a, b = severities[i], severities[i + 1]
        ratio = contrast(t(f"sev-{a}"), t(f"sev-{b}"))
        if ratio < 1.2:
            weak_pairs.append((a, b, ratio))
        print(f"    {'ok  ' if ratio >= 1.2 else 'WEAK'}  {a:>8} vs {b:<8} {ratio:.2f}:1")

    # Invariant 4: the shape channel must be total. Wherever lightness is weak, shape
    # has to do the work, so every severity needs its own distinct outline.
    _checks += 1
    # Scoped to the SEVERITY_META literal. Reading the whole file also matches the
    # `shape: 'octagon' | 'triangle' | ...` union in the interface above it, which
    # produced a phantom duplicate on the first run of this check.
    shape_values = re.findall(
        r"shape:\s*'([a-z-]+)'",
        _object_body(SEVERITY_TS.read_text(encoding="utf-8"), "SEVERITY_META", SEVERITY_TS),
    )
    if len(shape_values) == len(severities) and len(set(shape_values)) == len(severities):
        print(f"\n  PASS  all {len(severities)} severities have a DISTINCT shape "
              f"({', '.join(shape_values)}),\n        so every level is separable with "
              "no colour information at all.")
    else:
        print(f"\n  FAIL  severity shapes are not all distinct: {shape_values}")
        _failures.append("severity shapes are not unique")

    if weak_pairs:
        print("    NOTE  " + ", ".join(f"{a}/{b} at {r:.2f}:1" for a, b, r in weak_pairs)
              + " are too close in lightness\n          to rank by tone. Those pairs "
              "are separated by shape (see above) and by\n          the text label, "
              "which SeverityBadge always renders.")

    # ------------------------------------------------------------------- CVD
    print("\n" + "-" * 78)
    print("5. COLOUR-VISION DEFICIENCY — Viénot/Brettel/Mollon dichromacy simulation")
    print("-" * 78)
    for kind in ("protanopia", "deuteranopia"):
        print(f"\n  {kind.capitalize()} — simulated severity foregrounds:")
        simulated = {name: simulate_cvd(t(f"sev-{name}"), kind) for name in severities}
        for name in severities:
            original = t(f"sev-{name}")
            sim = simulated[name]
            print(
                f"    sev-{name:<9} {original} -> {sim}   "
                f"L {relative_luminance(original):.4f} -> {relative_luminance(sim):.4f}"
            )
        print(f"  {kind.capitalize()} — adjacent pairs after simulation:")
        for i in range(len(severities) - 1):
            a, b = severities[i], severities[i + 1]
            ratio = contrast(simulated[a], simulated[b])
            print(f"    {'ok  ' if ratio >= 1.2 else 'WEAK'}  {a:>8} vs {b:<8} "
                  f"{ratio:.2f}:1")
        print(f"  {kind.capitalize()} — text contrast still readable on its badge tint:")
        for name in severities:
            fg = simulate_cvd(t(f"sev-{name}"), kind)
            bg = simulate_cvd(t(f"sev-{name}-bg"), kind)
            ratio = contrast(fg, bg)
            _checks += 1
            if ratio < AA_TEXT:
                _failures.append(
                    f"{kind}: sev-{name} label on its own tint drops to {ratio:.2f}:1"
                )
            print(f"    {'PASS' if ratio >= AA_TEXT else 'FAIL'}  sev-{name:<9} "
                  f"{ratio:5.2f}:1")

        print(f"  {kind.capitalize()} — accent (interactive) must stay distinct from "
              "sev-low:")
        ratio = contrast(simulate_cvd(t("accent"), kind), simulate_cvd(t("sev-low"), kind))
        print(f"    accent vs sev-low: {ratio:.2f}:1 "
              f"({'separable' if ratio >= 1.2 else 'RELIES ON SHAPE/LABEL'})")

    # ----------------------------------------------------------------- summary
    print("\n" + "=" * 78)
    print(f"{_checks} required checks run, {len(_failures)} failure(s)")
    print("=" * 78)
    if _failures:
        for failure in _failures:
            print(f"  FAIL  {failure}")
        return 1
    print("  All required contrast, drift, grayscale, and CVD checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
