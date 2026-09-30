"""friday · tests/unit/test_voice_tools.py

The two local voice tools linked 2026-09-29: jobs_status (a deterministic
digest over the Jobs command center; a blocked ~/Downloads read must answer, not
hang) and open_obsidian (vault or a named note; failures are spoken, not raised).
"""

import asyncio

import pytest

from adapters import vault
from integrations import jobs, jobs_voice

OVERVIEW = {
    "latest": "2026-09-28",
    "summary": {"total": 12, "approved": 4, "skipped": 2, "undecided": 6, "needs_you": 3},
    "code_queue": 1,
    "pipeline": {"total": 5, "by_status": {"applied": 3, "rejected": 2}},
}


async def test_jobs_status_reads_the_latest_batch(monkeypatch) -> None:
    monkeypatch.setattr(jobs, "overview", lambda: OVERVIEW)
    out = await jobs_voice.status("", "how's my job search")
    assert "2026-09-28: 12 roles, 4 approved, 2 skipped, 6 undecided" in out
    assert "3 need your answers" in out and "1 queued for submission" in out
    assert "tracker: 5 applications (3 applied, 2 rejected)" in out


async def test_jobs_status_with_no_batches(monkeypatch) -> None:
    empty = {**OVERVIEW, "latest": ""}
    monkeypatch.setattr(jobs, "overview", lambda: empty)
    assert "no job batches yet" in await jobs_voice.status("", "show my jobs")


async def test_jobs_status_times_out_instead_of_hanging(monkeypatch) -> None:
    monkeypatch.setattr(jobs_voice, "_TIMEOUT_S", 0.05)

    def blocked():  # macOS TCC holding the ~/Downloads read
        import time

        time.sleep(0.5)

    monkeypatch.setattr(jobs, "overview", blocked)
    out = await asyncio.wait_for(jobs_voice.status("", "jobs?"), 1)
    assert "didn't answer in time" in out


async def test_jobs_status_read_failure_is_spoken(monkeypatch) -> None:
    def broken():
        raise PermissionError("denied")

    monkeypatch.setattr(jobs, "overview", broken)
    assert "isn't readable" in await jobs_voice.status("", "jobs?")


@pytest.mark.parametrize(
    ("utterance", "note"),
    [
        ("open my notes", ""),
        ("open the note called sales engine", "sales engine"),
        ("Open the note named 'Weekly Review'.", "Weekly Review"),
    ],
)
async def test_open_obsidian_vault_or_named_note(monkeypatch, utterance, note) -> None:
    opened = []
    monkeypatch.setattr(vault, "open_in_obsidian", lambda n="": opened.append(n) or "ok")
    assert await vault.open_tool("", utterance) == "ok"
    assert opened == [note]


async def test_open_obsidian_failure_is_spoken(monkeypatch) -> None:
    def fail(note=""):
        raise ValueError("Obsidian not installed")

    monkeypatch.setattr(vault, "open_in_obsidian", fail)
    out = await vault.open_tool("", "open my notes")
    assert "wouldn't open" in out and "Obsidian not installed" in out


def test_both_tools_are_registered_safe() -> None:
    from config.tools import load_tools

    tools = {t.name: t for t in load_tools()}
    assert tools["jobs_status"].adapter == "integrations.jobs_voice:status"
    assert tools["open_obsidian"].adapter == "adapters.vault:open_tool"
    assert tools["jobs_status"].risk == tools["open_obsidian"].risk == "safe"
    # the only n8n-backed tool is the Friday-owned summary workflow
    assert [t.name for t in tools.values() if t.webhook_path] == ["send_summary"]
