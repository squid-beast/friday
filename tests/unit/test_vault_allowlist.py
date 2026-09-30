"""friday · tests/unit/test_vault_allowlist.py

Vault path allowlist (TDD — written before adapters/vault.py). Every read stays
inside VAULT_PATH; escapes, symlinks out, hidden dirs, and VAULT_EXCLUDE folders
must fail. The only write is append_inbox, and it only ever touches _inbox/.
"""

from pathlib import Path

import pytest

from config.settings import get_settings


@pytest.fixture
def vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "vault"
    (root / "projects").mkdir(parents=True)
    (root / "private").mkdir()
    (root / ".obsidian").mkdir()
    (root / "projects" / "receivly.md").write_text(
        "# Receivly\nQuoted the Receivly client $1500 for BookYourSlot setup.\n"
    )
    (root / "private" / "diary.md").write_text("off limits secret\n")
    (root / ".obsidian" / "app.md").write_text("editor config secret\n")
    (tmp_path / "outside.md").write_text("outside the vault\n")
    (root / "link-out.md").symlink_to(tmp_path / "outside.md")
    monkeypatch.setenv("VAULT_PATH", str(root))
    monkeypatch.setenv("VAULT_EXCLUDE", "private")
    get_settings.cache_clear()
    yield root
    get_settings.cache_clear()


# --- resolve / read_note: escapes must fail ---


def test_read_inside_vault_ok(vault: Path) -> None:
    from adapters.vault import read_note

    assert "Receivly" in read_note("projects/receivly.md")


@pytest.mark.parametrize(
    "attempt",
    [
        "../outside.md",
        "projects/../../outside.md",
        "/etc/passwd",
        "../../../../etc/passwd",
    ],
)
def test_escape_attempts_fail(vault: Path, attempt: str) -> None:
    from adapters.vault import read_note

    with pytest.raises(ValueError):
        read_note(attempt)


def test_symlink_pointing_outside_fails(vault: Path) -> None:
    from adapters.vault import read_note

    with pytest.raises(ValueError):
        read_note("link-out.md")


def test_excluded_folder_fails(vault: Path) -> None:
    from adapters.vault import read_note

    with pytest.raises(ValueError, match="off-limits"):
        read_note("private/diary.md")


def test_hidden_folder_fails(vault: Path) -> None:
    from adapters.vault import read_note

    with pytest.raises(ValueError):
        read_note(".obsidian/app.md")


def test_missing_note_fails(vault: Path) -> None:
    from adapters.vault import read_note

    with pytest.raises(ValueError, match="no such note"):
        read_note("projects/ghost.md")


# --- search: never surfaces excluded/hidden/outside content ---


async def test_search_finds_note(vault: Path) -> None:
    from adapters.vault import search

    hits = await search("what did I quote the Receivly client?")
    assert hits and hits[0].path == "projects/receivly.md"
    assert "1500" in hits[0].snippet


async def test_search_never_leaks_excluded_or_hidden(vault: Path) -> None:
    from adapters.vault import search

    for query in ("off limits secret", "editor config secret", "outside the vault"):
        assert await search(query) == []


# --- append_inbox: the ONLY write, always lands in _inbox/ ---


def test_append_inbox_writes_only_inside_inbox(vault: Path) -> None:
    from adapters.vault import append_inbox

    rel = append_inbox("follow up with the dentist lead on Friday")
    target = vault / rel
    assert target.is_relative_to(vault / "_inbox")
    assert "dentist lead" in target.read_text()


def test_append_inbox_appends_not_overwrites(vault: Path) -> None:
    from adapters.vault import append_inbox

    append_inbox("first note")
    rel = append_inbox("second note")
    text = (vault / rel).read_text()
    assert "first note" in text and "second note" in text
    assert text.index("first note") < text.index("second note")


def test_append_inbox_rejects_empty(vault: Path) -> None:
    from adapters.vault import append_inbox

    with pytest.raises(ValueError):
        append_inbox("   ")


# --- the Obsidian hand-off (we don't reimplement Obsidian's browsing/graph) ---


def test_open_in_obsidian_builds_the_vault_url(vault: Path) -> None:
    from adapters.vault import open_in_obsidian

    calls = []

    def run(cmd, **kw):
        calls.append(cmd)
        return type("R", (), {"returncode": 0, "stderr": ""})()

    said = open_in_obsidian(run=run)
    assert calls[0] == ["open", "obsidian://open?vault=vault"]  # tmp vault dir name
    assert "Obsidian" in said


def test_open_in_obsidian_escapes_a_note_name(vault: Path) -> None:
    from adapters.vault import open_in_obsidian

    calls = []
    open_in_obsidian("med spa & co", run=lambda cmd, **kw: calls.append(cmd) or
                     type("R", (), {"returncode": 0, "stderr": ""})())
    assert calls[0][1].endswith("&file=med%20spa%20%26%20co")  # never breaks the URL


def test_open_in_obsidian_surfaces_failure(vault: Path) -> None:
    from adapters.vault import open_in_obsidian

    with pytest.raises(ValueError, match="Obsidian is not installed"):
        open_in_obsidian(run=lambda cmd, **kw: type(
            "R", (), {"returncode": 1, "stderr": "Obsidian is not installed"})())
