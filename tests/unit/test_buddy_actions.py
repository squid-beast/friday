"""friday · tests/unit/test_buddy_actions.py

Phase 4 local actions: today's plan lives in sir's Obsidian daily note
(daily/YYYY/YYYY-MM-DD.md, "## Friday plan" checkboxes) and respects the vault
allowlist; open/search opens only INSTALLED apps (never guesses) and URL-encodes
searches into fixed templates — argument lists, no shell.
"""

import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from adapters import mac_actions, vault_plan
from config.settings import get_settings

NOW = time.mktime((2026, 9, 30, 10, 0, 0, 0, 0, -1))


@pytest.fixture
def vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("VAULT_PATH", str(tmp_path))
    monkeypatch.setenv("VAULT_EXCLUDE", "")
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


def test_plan_creates_the_daily_note_and_appends_in_order(vault: Path) -> None:
    assert vault_plan.add("call the bank", NOW) == "daily/2026/2026-09-30.md"
    vault_plan.add("gym at six.", NOW)
    note = (vault / "daily/2026/2026-09-30.md").read_text()
    assert note.splitlines()[:5] == ["# 2026-09-30", "", "## Friday plan",
                                     "- [ ] call the bank", "- [ ] gym at six"]
    assert vault_plan.items(NOW) == [(False, "call the bank"), (False, "gym at six")]


def test_plan_joins_an_existing_daily_note_without_touching_other_sections(vault: Path) -> None:
    note = vault / "daily/2026/2026-09-30.md"
    note.parent.mkdir(parents=True)
    note.write_text("# Wed\n\n## Friday plan\n- [x] stretch\n\n## Journal\nslept ok\n")
    vault_plan.add("ship the README", NOW)
    text = note.read_text()
    assert "- [x] stretch\n- [ ] ship the README\n\n## Journal\nslept ok" in text
    assert vault_plan.items(NOW) == [(True, "stretch"), (False, "ship the README")]


def test_plan_refuses_an_off_limits_daily_folder(vault: Path, monkeypatch) -> None:
    monkeypatch.setenv("VAULT_EXCLUDE", "daily")
    get_settings.cache_clear()
    with pytest.raises(ValueError, match="off-limits"):
        vault_plan.add("secret", NOW)


async def test_plan_tool_adds_or_reads(vault: Path) -> None:
    out = await vault_plan.plan("", "Add call the bank to today's plan")
    assert out.startswith("added 'call the bank'")
    assert "call the bank" in await vault_plan.plan("", "what's on today's plan?")


async def test_plan_tool_empty_read(vault: Path) -> None:
    assert "empty" in await vault_plan.plan("", "read me today's plan")


@pytest.mark.parametrize(("utterance", "url"), [
    ("search YouTube for lo-fi beats", "https://www.youtube.com/results?search_query=lo-fi+beats"),
    ("look up rust async on github", "https://github.com/search?q=rust+async"),
    ("google flights to Austin", "https://www.google.com/search?q=flights+to+Austin"),
    ("search for best espresso machine", "https://www.google.com/search?q=best+espresso+machine"),
    ("find coffee near me on maps", "https://www.google.com/maps/search/coffee+near+me"),
])
def test_search_urls_are_encoded_into_fixed_templates(utterance: str, url: str) -> None:
    assert mac_actions.search_url(utterance) == url


def test_app_names_resolve_only_to_installed_apps() -> None:
    apps = {"slack": "Slack", "visual studio code": "Visual Studio Code",
            "notes": "Notes", "notion": "Notion"}
    assert mac_actions.resolve_app("Slack", apps) == "Slack"
    assert mac_actions.resolve_app("code", apps) == "Visual Studio Code"
    assert mac_actions.resolve_app("no", apps) is None  # ambiguous (notes/notion): refuse
    assert mac_actions.resolve_app("photoshop", apps) is None  # not installed: never guess


async def test_open_or_search_runs_open_with_an_argument_list() -> None:
    calls = []

    def run(cmd, **kw):
        calls.append(cmd)
        return SimpleNamespace(returncode=0)

    apps = lambda: {"slack": "Slack"}  # noqa: E731
    assert await mac_actions.open_or_search("", "open Slack", run=run, apps=apps) == "opened Slack"
    assert calls[-1] == ["open", "-a", "Slack"]
    out = await mac_actions.open_or_search("", "search YouTube for jazz; rm -rf ~", run=run,
                                           apps=apps)
    assert calls[-1][0] == "open" and "rm+-rf" in calls[-1][1] and out.startswith("opened")
    assert "can't find" in await mac_actions.open_or_search("", "open Photoshop", run=run,
                                                            apps=apps)
