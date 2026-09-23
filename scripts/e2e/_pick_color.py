"""Helper: find the nearest colour to a starting hex that meets a contrast target.

Used to repair the tokens that `check_contrast.py` measured as failing, so the
replacements are computed against the real backgrounds rather than eyeballed. Walks
the colour darker along its own hue (scaling channels toward black) and reports the
first value that clears every requested (background, minimum) pair.
"""

from __future__ import annotations

import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))

from check_contrast import contrast, parse_hex, relative_luminance, to_hex  # noqa: E402


def darken(hex_colour: str, factor: float) -> str:
    r, g, b = parse_hex(hex_colour)
    return to_hex((r * factor, g * factor, b * factor))


def search(name: str, start: str, requirements: list[tuple[str, float]]) -> str:
    factor = 1.0
    while factor > 0.2:
        candidate = darken(start, factor)
        if all(contrast(candidate, bg) >= minimum for bg, minimum in requirements):
            print(f"\n{name}: {start} -> {candidate}  (factor {factor:.3f}, "
                  f"L {relative_luminance(start):.4f} -> "
                  f"{relative_luminance(candidate):.4f})")
            for bg, minimum in requirements:
                print(f"    vs {bg}: {contrast(candidate, bg):.2f}:1 (min {minimum})")
            return candidate
        factor -= 0.005
    raise SystemExit(f"no candidate found for {name}")


CANVAS = "#ffffff"
SURFACE = "#f7f8fa"
SUNKEN = "#f2f4f7"

if __name__ == "__main__":
    # Headroom above the bare minimum so a later tint tweak does not silently
    # re-break the pair.
    search("ink-muted", "#737d8c", [(CANVAS, 4.6), (SURFACE, 4.6), (SUNKEN, 4.6)])
    search("sev-unknown", "#6b7480", [(CANVAS, 4.6), (SURFACE, 4.6), ("#f5f6f8", 4.6)])
    search("control-border", "#c9cfd8", [(CANVAS, 3.05), (SURFACE, 3.05), (SUNKEN, 3.05)])
    search("agent documentation fill", "#8d9daf", [(CANVAS, 3.1)])
    search("agent test_gap fill", "#6f8296", [(CANVAS, 3.1)])
