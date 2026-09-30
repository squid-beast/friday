"""adapters/apps.py — the wake app launch. `open` commands are built right,
failures are logged (not silently swallowed), disabled/empty configs no-op, and
the tool speaks what it opened."""

import types

import adapters.apps as apps
from adapters.apps import launch_apps
from config.settings import Settings


def _settings(**kw):
    base = dict(
        wake_apps_enabled=True,
        wake_launch_spotify=True,
        wake_urls="https://a.com,https://b.com",
    )
    base.update(kw)
    return Settings(**base)


def _ok(cmd, **kw):
    return types.SimpleNamespace(returncode=0, stderr="")


def test_launch_opens_spotify_then_chrome_tabs():
    calls = []

    def run(cmd, **kw):
        calls.append(cmd)
        return _ok(cmd)

    launched = launch_apps(settings=_settings(), run=run)
    assert calls[0] == ["open", "-a", "Spotify"]
    assert calls[1] == ["open", "-a", "Google Chrome", "https://a.com", "https://b.com"]
    assert launched == ["Spotify", "Chrome (2 tabs)"]


def test_disabled_is_a_noop():
    calls = []
    out = launch_apps(settings=_settings(wake_apps_enabled=False),
                      run=lambda c, **k: calls.append(c) or _ok(c))
    assert out == [] and calls == []


def test_no_spotify_when_off():
    calls = []
    launch_apps(settings=_settings(wake_launch_spotify=False),
                run=lambda c, **k: calls.append(c) or _ok(c))
    assert all("Spotify" not in c for c in calls)


def test_empty_urls_skips_chrome():
    calls = []
    launch_apps(settings=_settings(wake_urls=" , ,"),
                run=lambda c, **k: calls.append(c) or _ok(c))
    assert calls == [["open", "-a", "Spotify"]]  # only Spotify, no Chrome tabs


def test_failed_open_is_not_reported_launched():
    # `open` returns non-zero (e.g. app missing) -> not counted, not raised.
    def boom(cmd, **kw):
        return types.SimpleNamespace(returncode=1, stderr="Unable to find application")

    launched = launch_apps(settings=_settings(), run=boom)
    assert launched == []  # nothing claimed as opened when open fails


async def test_tool_reports_what_it_opened(monkeypatch):
    monkeypatch.setattr(apps, "launch_apps", lambda: ["Spotify", "Chrome (4 tabs)"])
    assert "Spotify and Chrome (4 tabs)" in await apps.launch("", "open my apps")


async def test_tool_when_disabled(monkeypatch):
    monkeypatch.setattr(apps, "launch_apps", lambda: [])
    assert "switched off" in await apps.launch("", "open my apps")
