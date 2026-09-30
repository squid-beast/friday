"""friday · tests/unit/test_ui.py

STRICT UI validation over the SvelteKit source (ui/src) + built output
(ui/build). Machine-checked design rules, not vibes:
- WCAG contrast COMPUTED from the token values in app.css (AA/AAA).
- Color flows ONLY through :root tokens — no stray hex/rgb in any component.
- Accessibility: labels, live regions, decorative aria-hidden, one dashboard.
- Touch-safe CSS remains available, even though the dashboard is voice-first.
- Self-contained: zero external resources at runtime (secret project).
"""

import re
from pathlib import Path

import pytest

_UI = Path(__file__).resolve().parents[2] / "ui"
CSS = (_UI / "src" / "app.css").read_text(encoding="utf-8")
LAYOUT = (_UI / "src" / "routes" / "+layout.svelte").read_text(encoding="utf-8")
SOURCES = {p.relative_to(_UI).as_posix(): p.read_text(encoding="utf-8")
           for p in list((_UI / "src").rglob("*.svelte"))
           + list((_UI / "src").rglob("*.js")) + [_UI / "src" / "app.css"]}


def _tokens(css: str) -> dict[str, str]:
    root = re.search(r":root\s*\{(.*?)\}", css, re.DOTALL).group(1)
    return dict(re.findall(r"--([a-z-]+):\s*(#[0-9a-fA-F]{6})", root))


def _luminance(hex_color: str) -> float:
    def channel(value: int) -> float:
        c = value / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(fg: str, bg: str) -> float:
    lighter, darker = sorted((_luminance(fg), _luminance(bg)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


TOKENS = _tokens(CSS)


def test_the_token_set_is_complete_and_lives_in_one_file() -> None:
    assert set(TOKENS) >= {
        "bg", "surface", "line", "ink", "ink-dim", "accent", "accent-text", "accent-deep",
    }
    others = [n for n, s in SOURCES.items() if ":root" in s and n != "src/app.css"]
    assert others == [], f"tokens must live ONLY in app.css, found :root in {others}"


@pytest.mark.parametrize(
    ("fg", "bg", "minimum"),
    [
        ("ink", "bg", 7.0),
        ("ink", "surface", 7.0),
        ("ink-dim", "bg", 4.5),
        ("ink-dim", "surface", 4.5),
        ("accent-text", "bg", 4.5),
        ("accent-text", "surface", 4.5),
        ("ink", "accent-deep", 4.5),
    ],
)
def test_wcag_contrast_computed_not_assumed(fg: str, bg: str, minimum: float) -> None:
    ratio = contrast(TOKENS[fg], TOKENS[bg])
    assert ratio >= minimum, f"{fg} on {bg} = {ratio:.2f}:1, needs {minimum}:1"


@pytest.mark.parametrize("name", sorted(SOURCES))
def test_color_flows_only_through_tokens(name: str) -> None:
    body = SOURCES[name]
    if name == "src/app.css":
        body = body[body.index("}"):]
    stray_hex = re.findall(r"#[0-9a-fA-F]{3,8}\b", body)
    assert stray_hex == [], f"{name}: hardcoded colors {stray_hex}"
    stray_rgb = [m for m in re.findall(r"rgba?\([^)]+\)", body)
                 if not m.startswith("rgba(0,0,0,")]
    assert stray_rgb == [], f"{name}: non-token rgb() {stray_rgb}"


def test_monospace_brand_typeface_and_tracking() -> None:
    assert "ui-monospace" in CSS
    assert re.search(r"letter-spacing:\s*\.3\d*em", CSS)


def test_touch_targets_meet_44px() -> None:
    for selector in ("input", "button"):
        block = re.search(selector + r"\s*\{[^}]*\}", CSS).group(0)
        assert "min-height: 44px" in block, f"sub-44px {selector} in app.css"


# Lohith, 2026-09-28: the Jobs command center (/jobs) is the ONE place with
# buttons (approve/skip/answer/open). The cockpit itself stays voice-only.
JOBS_SCOPE = ("src/routes/jobs/", "src/lib/components/jobs/", "src/lib/jobs.js")


def test_single_dashboard_is_voice_only_and_button_free() -> None:
    dash = SOURCES["src/routes/+page.svelte"]
    everything = "\n".join(s for n, s in SOURCES.items() if not n.startswith(JOBS_SCOPE))
    assert "<nav" not in LAYOUT
    assert 'aria-label="Friday status"' in LAYOUT
    assert "toggleMacSession" not in everything
    assert "src/lib/components/Composer.svelte" not in SOURCES
    assert "<Log />" in dash
    for panel in ("NowPanel", "MetricsPanel", "TodayPanel", "JobsPanel", "HudPanel"):
        assert panel in dash, f"dashboard missing {panel}"
    for parked in ("StudioPanel", "GesturePanel"):  # parked 2026-09-29: kept, not mounted
        assert parked not in dash, f"{parked} is parked and must not poll"
        assert f"src/lib/components/{parked}.svelte" in SOURCES
    assert "wake_phrase_active" in dash
    assert "<button" not in everything
    assert 'role="button"' not in everything
    assert "onclick=" not in everything


def test_conversation_is_labelled_live_and_animated() -> None:
    log = SOURCES["src/lib/components/Log.svelte"]
    assert 'aria-live="polite"' in log
    assert "transition:fly" in log
    assert "recentConversation" in log and "setInterval" in log  # fed by the brain's store
    assert "src/lib/voice.js" not in SOURCES  # orphaned browser-voice module removed
    assert "Friday will show your most recent spoken turns here." in log


def test_decoration_is_hidden_from_screen_readers() -> None:
    assert 'class="ruler" aria-hidden="true"' in LAYOUT
    metrics = SOURCES["src/lib/components/MetricsPanel.svelte"]
    assert 'aria-hidden="true"' in metrics


def test_dashboard_keeps_obsidian_passive_and_truthful() -> None:
    hud = SOURCES["src/lib/components/HudPanel.svelte"]
    assert "Open in Obsidian" not in hud
    assert "Friday can answer from your notes without copying them out of Obsidian." in hud
    assert "use the wake phrase above" in hud


def test_notch_keyboard_and_dvh_are_respected() -> None:
    everything = "\n".join(SOURCES.values())
    assert "env(safe-area-inset-top)" in everything
    assert "100dvh" in everything


@pytest.mark.parametrize("name", sorted(SOURCES))
def test_zero_external_resources_in_source(name: str) -> None:
    body = SOURCES[name]
    assert not re.search(r'(?:src|href)="https?://', body), name
    assert "@import" not in body and "url(http" not in body, name
    assert not re.search(r'from\s+"https?://', body), name


def test_build_output_exists_and_is_self_contained() -> None:
    build = _UI / "build"
    assert (build / "index.html").is_file(), "run: cd ui && npm run build"
    shell = (build / "index.html").read_text(encoding="utf-8")
    assert not re.search(r'(?:src|href)="https?://', shell)
    assert "/_app/" in shell


def test_jobs_command_center_is_the_only_button_surface_and_accessible() -> None:
    page = SOURCES["src/routes/jobs/+page.svelte"]
    row = SOURCES["src/lib/components/jobs/JobRow.svelte"]
    assert 'aria-label="Jobs command center"' in page
    assert 'aria-live="polite"' in page and 'aria-live="polite"' in row
    assert 'href="/"' in page, "jobs page must link back to the cockpit"
    assert "aria-label={`Approve #${role.n}`}" in row
    assert 'rel="noopener noreferrer"' in row
    assert 'href="/jobs"' in SOURCES["src/lib/components/JobsPanel.svelte"]
