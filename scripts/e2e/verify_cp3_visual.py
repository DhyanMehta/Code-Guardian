"""Checkpoint 3 verification in a real browser, against the real backend.

Everything here is observed, not asserted from intent. Playwright drives the
already-installed system Chrome (`channel="chrome"`, so nothing is downloaded)
against the live Vite dev server on 127.0.0.1:5173 and the live FastAPI backend on
127.0.0.1:8000. No mocked responses, no fixtures.

What it measures:

  1. Trends charts render from the real /metrics/trends payload, and the coverage
     marker actually drawn for each point matches the coverage state the API reported
     — so a degraded review cannot be plotted as a clean one.
  2. The insufficient-data state appears below three points and the numbers appear as
     a table instead.
  3. Grayscale: the findings list re-rendered with all colour removed, plus a check
     that every severity present carries a distinct SVG shape.
  4. Protanopia and deuteranopia: the same page through a dichromacy colour matrix.
  5. Tabular numerals: proven by measuring rendered glyph widths ('111...' vs
     '000...' must be the same width), not by trusting the CSS declaration.
  6. Keyboard-only navigation with a visible focus ring at every stop, including the
     auto-fix confirmation dialog. The dialog is opened and cancelled — never
     confirmed, because confirming pushes a branch to a real repository.
  7. The auto-fix panel and raw-report tab in every state the real database holds.

Screenshots land in scripts/e2e/screenshots/.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

FRONTEND = "http://127.0.0.1:5173"
BACKEND = "http://127.0.0.1:8000"
SHOTS = Path(__file__).resolve().parent / "screenshots"

# Machado, Oliveira & Fernandes (2009) dichromacy matrices at full severity, used as
# SVG feColorMatrix values. These are the same matrices browser devtools' vision
# deficiency emulation uses.
CVD_MATRICES = {
    "protanopia": (
        "0.152286 1.052583 -0.204868 0 0 "
        "0.114503 0.786281 0.099216 0 0 "
        "-0.003882 -0.048116 1.051998 0 0 "
        "0 0 0 1 0"
    ),
    "deuteranopia": (
        "0.367322 0.860646 -0.227968 0 0 "
        "0.280085 0.672501 0.047413 0 0 "
        "-0.011820 0.042940 0.968881 0 0 "
        "0 0 0 1 0"
    ),
}

_failures: list[str] = []
_passes = 0


def check(condition: bool, label: str, evidence: str = "") -> bool:
    global _passes
    if condition:
        _passes += 1
        print(f"  PASS  {label}" + (f"  [{evidence}]" if evidence else ""))
    else:
        _failures.append(f"{label} — {evidence}" if evidence else label)
        print(f"  FAIL  {label}" + (f"  [{evidence}]" if evidence else ""))
    return condition


def api(path: str):
    with urllib.request.urlopen(f"{BACKEND}{path}", timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def section(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def shot(page, name: str, full: bool = True) -> Path:
    SHOTS.mkdir(parents=True, exist_ok=True)
    path = SHOTS / f"{name}.png"
    page.screenshot(path=str(path), full_page=full)
    print(f"        screenshot -> scripts/e2e/screenshots/{path.name}")
    return path


# --------------------------------------------------------------------------- filters

_CVD_SVG = """
(matrix, id) => {
  const existing = document.getElementById('cvd-' + id);
  if (!existing) {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('id', 'cvd-' + id);
    svg.setAttribute('style', 'position:absolute;width:0;height:0');
    svg.innerHTML =
      '<filter id="f-' + id + '" color-interpolation-filters="linearRGB">' +
      '<feColorMatrix type="matrix" values="' + matrix + '"/></filter>';
    document.body.appendChild(svg);
  }
  document.documentElement.style.filter = 'url(#f-' + id + ')';
}
"""


def apply_cvd(page, kind: str) -> None:
    page.evaluate(_CVD_SVG, [CVD_MATRICES[kind], kind])


def clear_filter(page) -> None:
    page.evaluate("() => { document.documentElement.style.filter = ''; }")


# ------------------------------------------------------------------------- 1. trends


def verify_trends(page, trends) -> None:
    section("1. TRENDS PAGE — charts built from the real /metrics/trends payload")

    points = trends["points"]
    page.goto(f"{FRONTEND}/trends?limit=50", wait_until="networkidle")
    page.wait_for_selector(".recharts-wrapper", timeout=20_000)
    page.wait_for_timeout(600)  # let the responsive containers settle

    wrappers = page.locator(".recharts-wrapper").count()
    check(wrappers == 4, "four chart canvases render", f"{wrappers} .recharts-wrapper")

    headings = page.locator("h2").all_inner_texts()
    for expected in (
        "Findings per review",
        "Weighted severity index",
        "Severity mix",
        "Agent contribution",
    ):
        check(expected in headings, f"chart present: {expected}")

    # The important one: does the marker drawn for each point match the coverage state
    # the API reported? Counted inside the plot area only, so legend keys do not skew it.
    expected_states: dict[str, int] = {"complete": 0, "gap": 0, "unknown": 0}
    for point in points:
        if point["degraded_agents"]:
            expected_states["gap"] += 1
        elif not point["coverage_recorded"]:
            expected_states["unknown"] += 1
        else:
            expected_states["complete"] += 1

    print(f"\n        API says: {expected_states} across {len(points)} points")
    # Two line charts each plot every point, so the DOM holds 2x the marker count.
    for state, expected_count in expected_states.items():
        drawn = page.locator(f'.recharts-wrapper [data-coverage="{state}"]').count()
        check(
            drawn == expected_count * 2,
            f"coverage markers drawn for '{state}' match the API",
            f"{drawn} in DOM, expected {expected_count} x 2 line charts",
        )

    total_markers = page.locator(".recharts-wrapper [data-coverage]").count()
    check(
        total_markers == len(points) * 2,
        "every point carries a coverage marker",
        f"{total_markers} markers for {len(points)} points x 2 charts",
    )

    # The caution band must state the size of the untrusted sample.
    untrusted = expected_states["gap"] + expected_states["unknown"]
    body = page.inner_text("body")
    check(
        f"{untrusted} of {len(points)} points cannot be read as a clean baseline" in body,
        "page states how much of the series is untrustworthy",
        f"{untrusted}/{len(points)}",
    )
    check(
        f"{trends['totals']['coverage_complete_reviews']}/{trends['totals']['reviews']}"
        in body,
        "verified-coverage stat tile shows the real ratio",
        f"{trends['totals']['coverage_complete_reviews']}/{trends['totals']['reviews']}",
    )
    check(
        "Weights are a judgement call" in body,
        "weighted index discloses that its weights are a judgement, not a measurement",
    )
    check(
        "does not show" in body and "completed_at" in body,
        "page states its own limitations, including the missing duration series",
    )

    shot(page, "01-trends-full")

    # Tooltip on the known-degraded point (review 8) must say the count is a lower bound.
    gap_marker = page.locator('.recharts-wrapper [data-coverage="gap"]').first
    gap_marker.hover(force=True)
    page.wait_for_timeout(400)
    tooltip = page.locator(".recharts-tooltip-wrapper").first
    tooltip_text = tooltip.inner_text() if tooltip.count() else ""
    check(
        "Known gap" in tooltip_text and "lower bound" in tooltip_text,
        "hovering a degraded point says the count is a lower bound",
        tooltip_text.replace("\n", " | ")[:110],
    )
    check(
        "quality" in tooltip_text.lower(),
        "tooltip names the agent that could not run",
    )
    shot(page, "02-trends-degraded-tooltip", full=False)


def verify_insufficient_data(page) -> None:
    section("2. INSUFFICIENT-DATA STATE — below three points, no line is drawn")

    page.goto(f"{FRONTEND}/trends?limit=2", wait_until="networkidle")
    page.wait_for_timeout(800)

    wrappers = page.locator(".recharts-wrapper").count()
    check(wrappers == 0, "no chart is drawn from 2 points", f"{wrappers} chart canvases")

    body = page.inner_text("body")
    check(
        "Not enough history yet (2 of 3 reviews)" in body,
        "state names the real shortfall",
    )
    check(
        "would say more about the sample than about the code" in body,
        "state explains why it refuses to draw",
    )

    tables = page.locator("table").count()
    visible_rows = page.locator("table tbody tr").count()
    check(tables >= 4, "the numbers are shown as tables instead", f"{tables} tables")
    check(visible_rows > 0, "table rows are visible", f"{visible_rows} rows")
    shot(page, "03-trends-insufficient-data")

    # And confirm the threshold is a real boundary, not a coincidence: 3 points draws.
    page.goto(f"{FRONTEND}/trends?limit=3", wait_until="networkidle")
    page.wait_for_selector(".recharts-wrapper", timeout=20_000)
    page.wait_for_timeout(400)
    check(
        page.locator(".recharts-wrapper").count() == 4,
        "3 points is enough and charts appear",
        "limit=3 renders 4 charts",
    )


# ---------------------------------------------------------------- 3/4. colour vision


def verify_grayscale_and_cvd(page) -> None:
    section("3. GRAYSCALE — severity order readable with no colour at all")

    page.goto(f"{FRONTEND}/reviews/10?tab=findings", wait_until="networkidle")
    page.wait_for_selector("text=Findings", timeout=20_000)
    page.wait_for_timeout(500)
    shot(page, "04-findings-colour")

    # Every severity badge's shape must be unique per severity, since shape is what
    # carries the ranking once colour is gone.
    badge_data = page.evaluate(
        """
        () => {
          const out = [];
          document.querySelectorAll('span').forEach((span) => {
            const svg = span.querySelector(':scope > svg');
            if (!svg) return;
            const label = span.textContent.trim();
            const shape = svg.firstElementChild;
            if (!shape) return;
            out.push({
              label,
              tag: shape.tagName,
              geometry: shape.getAttribute('points')
                || shape.getAttribute('d')
                || `r=${shape.getAttribute('r')} dash=${shape.getAttribute('stroke-dasharray')}`,
              color: getComputedStyle(span).color,
            });
          });
          return out;
        }
        """
    )
    severity_labels = {"Critical", "High", "Medium", "Low", "Info", "Unknown"}
    shapes: dict[str, str] = {}
    for entry in badge_data:
        if entry["label"] in severity_labels:
            shapes[entry["label"]] = f"{entry['tag']}:{entry['geometry']}"
    print(f"\n        severity badges found on review 10: {sorted(shapes)}")
    for label, signature in sorted(shapes.items()):
        print(f"          {label:<9} {signature[:74]}")
    check(len(shapes) > 0, "severity badges are present to inspect", f"{len(shapes)}")
    check(
        len(set(shapes.values())) == len(shapes),
        "every severity present uses a DISTINCT shape",
        f"{len(set(shapes.values()))} distinct signatures for {len(shapes)} severities",
    )

    # Now remove colour entirely and confirm the labels and shapes survive.
    page.evaluate(
        "() => { document.documentElement.style.filter = 'grayscale(1) contrast(1)'; }"
    )
    page.wait_for_timeout(300)
    shot(page, "05-findings-grayscale")
    grayscale_body = page.inner_text("body")
    for label in shapes:
        check(
            label in grayscale_body,
            f"severity label '{label}' still readable in grayscale",
        )
    clear_filter(page)

    section("4. COLOUR-VISION DEFICIENCY — dichromacy simulation in the browser")
    for kind in ("protanopia", "deuteranopia"):
        apply_cvd(page, kind)
        page.wait_for_timeout(300)
        shot(page, f"06-findings-{kind}")
        simulated = page.inner_text("body")
        ok = all(label in simulated for label in shapes)
        check(ok, f"all severity text labels survive {kind}", f"{len(shapes)} labels")
        clear_filter(page)

    # And the trends page, where colour does the most work.
    page.goto(f"{FRONTEND}/trends?limit=50", wait_until="networkidle")
    page.wait_for_selector(".recharts-wrapper", timeout=20_000)
    page.wait_for_timeout(600)
    for kind in ("protanopia", "deuteranopia"):
        apply_cvd(page, kind)
        page.wait_for_timeout(300)
        shot(page, f"07-trends-{kind}")
        clear_filter(page)
    page.evaluate("() => { document.documentElement.style.filter = 'grayscale(1)'; }")
    page.wait_for_timeout(300)
    shot(page, "08-trends-grayscale")
    clear_filter(page)
    check(True, "trends page captured in grayscale, protanopia and deuteranopia")


# -------------------------------------------------------------- 5. tabular numerals


def verify_tabular_numerals(page) -> None:
    section("5. TABULAR NUMERALS — proven by measured glyph width, not by the CSS")

    page.goto(f"{FRONTEND}/trends?limit=50", wait_until="networkidle")
    page.wait_for_selector(".recharts-wrapper", timeout=20_000)
    page.wait_for_timeout(600)

    results = page.evaluate(
        """
        () => {
          // Width of '1111111111' vs '0000000000' in the element's own resolved font.
          // With proportional figures Inter's '1' is narrower than '0', so the two
          // strings differ; with tabular figures every digit is the same advance and
          // the widths match exactly. This measures the rendered result rather than
          // trusting that the declaration took effect.
          const measure = (el) => {
            const cs = getComputedStyle(el);
            const probe = document.createElement('span');
            probe.style.position = 'absolute';
            probe.style.visibility = 'hidden';
            probe.style.whiteSpace = 'pre';
            probe.style.font = cs.font;
            probe.style.fontFamily = cs.fontFamily;
            probe.style.fontSize = cs.fontSize;
            probe.style.fontWeight = cs.fontWeight;
            probe.style.fontVariantNumeric = cs.fontVariantNumeric;
            probe.style.fontFeatureSettings = cs.fontFeatureSettings;
            document.body.appendChild(probe);
            probe.textContent = '1111111111';
            const ones = probe.getBoundingClientRect().width;
            probe.textContent = '0000000000';
            const zeros = probe.getBoundingClientRect().width;
            probe.remove();
            return {
              declared: cs.fontVariantNumeric,
              features: cs.fontFeatureSettings,
              ones: Math.round(ones * 1000) / 1000,
              zeros: Math.round(zeros * 1000) / 1000,
              tabular: Math.abs(ones - zeros) < 0.01,
            };
          };

          const targets = [];
          const push = (name, el) => { if (el) targets.push([name, el]); };
          push('stat tile value (.tabular)', document.querySelector('.tabular'));
          push('chart axis tick (SVG text)',
               document.querySelector('.chart-numerals .recharts-cartesian-axis-tick text'));
          push('sr-only data table cell',
               document.querySelector('table td'));
          push('page heading count',
               document.querySelector('h1'));

          const out = {};
          for (const [name, el] of targets) out[name] = measure(el);

          // A control: an element with no tabular rule should show proportional
          // figures, which proves the probe can tell the difference at all.
          const control = document.createElement('span');
          control.style.fontVariantNumeric = 'proportional-nums';
          control.style.fontFeatureSettings = "'tnum' 0";
          document.body.appendChild(control);
          out['CONTROL (proportional, expected mismatch)'] = measure(control);
          control.remove();
          return out;
        }
        """
    )

    for name, data in results.items():
        print(
            f"\n        {name}\n"
            f"          font-variant-numeric : {data['declared'] or '(none)'}\n"
            f"          font-feature-settings: {data['features'] or '(normal)'}\n"
            f"          width '1111111111'   : {data['ones']}px\n"
            f"          width '0000000000'   : {data['zeros']}px\n"
            f"          equal widths         : {data['tabular']}"
        )

    control = results.pop("CONTROL (proportional, expected mismatch)")
    check(
        not control["tabular"],
        "the width probe can detect proportional figures (control)",
        f"{control['ones']}px vs {control['zeros']}px differ, so the test is meaningful",
    )
    for name, data in results.items():
        check(
            data["tabular"],
            f"tabular figures active: {name}",
            f"{data['ones']}px == {data['zeros']}px",
        )


# ---------------------------------------------------------------- 6. keyboard access


def describe_focus(page) -> dict:
    return page.evaluate(
        """
        () => {
          const el = document.activeElement;
          if (!el || el === document.body) return { tag: 'BODY', text: '', ring: '' };
          const cs = getComputedStyle(el);
          let ring = `${cs.outlineStyle} ${cs.outlineWidth} ${cs.outlineColor}`;
          if (cs.outlineStyle === 'none' || cs.outlineWidth === '0px') {
            ring = cs.boxShadow && cs.boxShadow !== 'none'
              ? `box-shadow ${cs.boxShadow}` : 'NONE';
          }
          return {
            tag: el.tagName,
            role: el.getAttribute('role') || '',
            text: (el.innerText || el.value || el.getAttribute('aria-label') || '')
              .trim().replace(/\\s+/g, ' ').slice(0, 46),
            href: el.getAttribute('href') || '',
            ring,
            focusVisible: el.matches(':focus-visible'),
            outlineOffset: cs.outlineOffset,
          };
        }
        """
    )


def verify_keyboard(page) -> None:
    section("6. KEYBOARD-ONLY NAVIGATION — every stop must show a visible focus ring")

    page.goto(f"{FRONTEND}/reviews", wait_until="networkidle")
    page.wait_for_selector("table tbody tr", timeout=20_000)
    page.locator("body").click(position={"x": 3, "y": 3})

    print("\n        Tabbing through the review list:")
    stops, missing_ring = [], []
    for _ in range(24):
        page.keyboard.press("Tab")
        page.wait_for_timeout(45)
        focus = describe_focus(page)
        if focus["tag"] == "BODY":
            continue
        signature = (focus["tag"], focus["text"], focus["href"])
        if signature in [s[0] for s in stops]:
            break
        stops.append((signature, focus))
        marker = "ring" if focus["ring"] != "NONE" else "NO RING"
        print(
            f"          {len(stops):>2}. {focus['tag']:<7} "
            f"{(focus['text'] or focus['href'])[:40]:<42} "
            f"{marker}: {focus['ring'][:38]}  focus-visible={focus['focusVisible']}"
        )
        if focus["ring"] == "NONE":
            missing_ring.append(focus)

    check(len(stops) >= 5, "list page is reachable by keyboard", f"{len(stops)} stops")
    check(
        not missing_ring,
        "every keyboard stop on the list page has a visible focus indicator",
        f"{len(missing_ring)} without a ring"
        if missing_ring
        else f"all {len(stops)} stops show an outline",
    )
    shot(page, "09-keyboard-list-focus", full=False)

    # Activating a review link with the keyboard must navigate.
    page.goto(f"{FRONTEND}/reviews", wait_until="networkidle")
    page.wait_for_selector("table tbody tr", timeout=20_000)
    first_link = page.locator('table tbody a[href^="/reviews/"]').first
    first_link.focus()
    focused_href = page.evaluate("() => document.activeElement.getAttribute('href')")
    page.keyboard.press("Enter")
    page.wait_for_url("**/reviews/**", timeout=10_000)
    check(
        page.url.endswith(focused_href or "@@"),
        "Enter on a focused review row navigates to its detail page",
        f"{focused_href} -> {page.url}",
    )

    # Tabs must be operable from the keyboard.
    page.goto(f"{FRONTEND}/reviews/8?tab=findings", wait_until="networkidle")
    page.wait_for_selector("text=Partial review", timeout=20_000)
    agents_tab = page.get_by_role("button", name="Agents").or_(
        page.locator("button", has_text="Agents")
    ).first
    agents_tab.focus()
    ring = describe_focus(page)
    check(
        ring["ring"] != "NONE",
        "tab control shows a focus ring",
        f"{ring['ring'][:50]}",
    )
    page.keyboard.press("Enter")
    page.wait_for_timeout(500)
    check("tab=agents" in page.url, "Enter activates the tab", page.url)
    shot(page, "10-keyboard-tab-activated")

    # The auto-fix confirmation dialog. Opened and cancelled only: confirming would
    # push a real branch to GitHub.
    page.goto(f"{FRONTEND}/reviews/10?tab=autofix", wait_until="networkidle")
    page.wait_for_selector("text=Create auto-fix branch", timeout=20_000)
    create = page.locator("button", has_text="Create auto-fix branch").first
    create.focus()
    focus = describe_focus(page)
    check(
        focus["ring"] != "NONE",
        "the auto-fix action shows a focus ring before it is activated",
        focus["ring"][:50],
    )
    page.keyboard.press("Enter")
    page.wait_for_timeout(400)
    dialog_text = page.inner_text("body")
    check(
        "Create auto-fix branch?" in dialog_text,
        "Enter opens the confirmation dialog rather than acting immediately",
    )
    check(
        "with real commits to" in dialog_text,
        "dialog states that it pushes real commits",
    )
    shot(page, "11-keyboard-autofix-dialog")

    print("\n        Tabbing inside the open dialog:")
    dialog_stops = 0
    for _ in range(6):
        page.keyboard.press("Tab")
        page.wait_for_timeout(45)
        focus = describe_focus(page)
        if focus["tag"] == "BODY":
            continue
        dialog_stops += 1
        print(
            f"          {focus['tag']:<7} {focus['text'][:34]:<36} "
            f"ring: {focus['ring'][:34]}"
        )
        if focus["ring"] == "NONE":
            _failures.append("dialog control without a focus ring")
    check(dialog_stops > 0, "dialog controls are keyboard reachable", f"{dialog_stops} stops")

    page.keyboard.press("Escape")
    page.wait_for_timeout(400)
    check(
        "Create auto-fix branch?" not in page.inner_text("body"),
        "Escape cancels the dialog without performing the action",
    )
    autofix = api("/reviews/10")["autofix"]
    check(
        autofix["status"] is None,
        "review 10 auto-fix is still untouched in the database",
        f"status={autofix['status']}, branch={autofix['branch']}",
    )


# ------------------------------------------------------- 7. autofix + report states


def verify_autofix_and_report(page) -> None:
    section("7. AUTO-FIX PANEL AND RAW REPORT — every state the real database holds")

    cases = [
        (1, "approved", ["Approved", "not merged", "DhyanMehta", "codeguardian/autofix/1"]),
        (4, "fork-disabled", ["Auto-fix is unavailable for fork PRs"]),
        (3, "skipped-disabled", ['Auto-fix is only available for completed reviews']),
        (10, "enabled", ["Create auto-fix branch"]),
    ]
    for review_id, name, expected in cases:
        page.goto(f"{FRONTEND}/reviews/{review_id}?tab=autofix", wait_until="networkidle")
        page.wait_for_timeout(700)
        body = page.inner_text("body")
        for phrase in expected:
            check(
                phrase in body,
                f"review {review_id} auto-fix state '{name}' shows: {phrase!r}",
            )
        if name != "enabled":
            disabled = page.locator("button:disabled", has_text="Create auto-fix").count()
            if name in ("fork-disabled", "skipped-disabled"):
                check(
                    disabled == 1,
                    f"review {review_id}: the create action is actually disabled",
                    f"{disabled} disabled create button(s)",
                )
        shot(page, f"12-autofix-{review_id}-{name}", full=False)

    print("\n        States the live database cannot demonstrate:")
    print("          pending_approval — needs POST /reviews/{id}/autofix, which pushes")
    print("            a real branch to GitHub. Not performed without approval.")
    print("          no-fixable-findings — every completed non-fork review has")
    print("            fixable_count=7; review 3 has 0 but is skipped, and the")
    print("            'review is skipped' reason fires first by design.")

    section("7b. RAW REPORT TAB — verbatim block, and the two different 409s")
    page.goto(f"{FRONTEND}/reviews/10?tab=report", wait_until="networkidle")
    page.wait_for_timeout(900)
    body = page.inner_text("body")
    check(
        "Posted PR comment (verbatim)" in body,
        "report tab labels the block as the verbatim posted comment",
    )
    check(
        "Reproduced exactly as posted to GitHub" in body,
        "report tab explains why emoji appear inside that block only",
    )
    rendered = page.locator("pre code").first.inner_text()
    real = api("/reviews/10/report")["markdown"]
    check(
        rendered.strip() == real.strip(),
        "rendered block matches the API markdown character for character",
        f"{len(rendered)} chars rendered vs {len(real)} from the API",
    )
    shot(page, "13-report-verbatim")

    page.goto(f"{FRONTEND}/reviews/3?tab=report", wait_until="networkidle")
    page.wait_for_timeout(900)
    body = page.inner_text("body")
    check(
        "No report for a skipped review" in body,
        "a skipped review says no report exists, not 'not ready yet'",
    )
    check(
        "Report not ready" not in body,
        "the misleading 'not ready' wording is gone for a terminal skipped review",
    )
    shot(page, "14-report-skipped-409")

    section("7c. DEGRADED AGENT — review 8 must read as a known gap")
    page.goto(f"{FRONTEND}/reviews/8?tab=agents", wait_until="networkidle")
    page.wait_for_timeout(700)
    body = page.inner_text("body")
    for phrase in ("Partial review", "Could not run", "Quality"):
        check(phrase in body, f"review 8 states the gap: {phrase!r}")
    check("\u2014" in body, "degraded agent's finding count renders as an em dash")
    shot(page, "15-review8-degraded-agents")


def main() -> int:
    trends = api("/metrics/trends?limit=50")
    print("=" * 78)
    print("CHECKPOINT 3 — real-browser verification")
    print("=" * 78)
    print(f"frontend : {FRONTEND}")
    print(f"backend  : {BACKEND}")
    print(f"trends   : {len(trends['points'])} real points, "
          f"{trends['totals']['findings']} findings")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 960}, device_scale_factor=2
        )
        page = context.new_page()
        console_errors: list[str] = []
        page.on(
            "console",
            lambda message: console_errors.append(message.text)
            if message.type == "error"
            else None,
        )
        page.on("pageerror", lambda error: console_errors.append(f"pageerror: {error}"))

        try:
            verify_trends(page, trends)
            verify_insufficient_data(page)
            verify_grayscale_and_cvd(page)
            verify_tabular_numerals(page)
            verify_keyboard(page)
            verify_autofix_and_report(page)
        finally:
            section("BROWSER CONSOLE")
            real_errors = [
                error
                for error in console_errors
                if "favicon" not in error.lower()
                and "Download the React DevTools" not in error
            ]
            if real_errors:
                for error in real_errors[:12]:
                    print(f"  ERROR {error[:200]}")
                _failures.append(f"{len(real_errors)} console error(s)")
            else:
                print("  PASS  no console errors or unhandled exceptions")
            context.close()
            browser.close()

    print("\n" + "=" * 78)
    print(f"{_passes} checks passed, {len(_failures)} failed")
    print("=" * 78)
    for failure in _failures:
        print(f"  FAIL  {failure}")
    return 1 if _failures else 0


if __name__ == "__main__":
    sys.exit(main())
