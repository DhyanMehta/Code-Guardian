"""Check current frontend token pairs and redundant severity labels/icons.

This is a static palette regression check, not a complete browser accessibility audit.
Run from the root: python -m scripts.e2e.check_contrast
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
CSS = ROOT / 'frontend/src/index.css'


def luminance(color):
    values = [int(color[i:i+2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in values]
    return sum(c * w for c, w in zip(linear, (.2126, .7152, .0722)))


def contrast(first, second):
    a, b = sorted((luminance(first), luminance(second)))
    return (b + .05) / (a + .05)


def main():
    tokens = dict(re.findall(r'--color-([a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{6})\s*;', CSS.read_text(encoding='utf-8')))
    failures = []
    checks = []
    # Text colors used by cards, timelines, metadata and navigation.
    for bg in ['canvas', 'neutral-900', 'neutral-850']:
        for fg in ['neutral-100', 'neutral-200', 'neutral-300', 'neutral-400', 'neutral-500', 'primary-400', 'tertiary-400', 'severity-medium']:
            checks.append((fg, bg, 4.5))
    for bg in ['primary-500', 'primary-600', 'primary-700']:
        checks.append(('neutral-white', bg, 4.5))
    for severity in ['critical', 'high', 'medium', 'low', 'info', 'unknown']:
        checks.append((f'severity-{severity}-text', f'severity-{severity}-bg', 4.5))
    checks.append(('primary-400', 'canvas', 3))
    for fg, bg, minimum in checks:
        ratio = contrast(tokens[fg], tokens[bg])
        ok = ratio >= minimum
        print(f'{"PASS" if ok else "FAIL"} {fg} on {bg}: {ratio:.2f}:1 (minimum {minimum}:1)')
        if not ok:
            failures.append(f'{fg} on {bg}')
    badge = (ROOT / 'frontend/src/components/common/SeverityBadge.tsx').read_text(encoding='utf-8')
    icons = re.findall(r'icon: (\w+),', badge)
    if len(icons) != 6 or len(set(icons)) != 6 or 'aria-label={`Severity: ${config.label}`}' not in badge or '{config.label.toUpperCase()}' not in badge:
        failures.append('Severity requires six distinct icons and accessible text labels')
    print(f'{len(checks) + 1} checks, {len(failures)} failures. Disabled control colors are excluded.')
    return int(bool(failures))


if __name__ == '__main__':
    raise SystemExit(main())
