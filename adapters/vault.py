"""jarvis-life-os · adapters/vault.py

leos-brain access. READ + APPEND-to-inbox only — nothing here can modify or
delete an existing note. Every path resolves inside VAULT_PATH; hidden dirs and
VAULT_EXCLUDE folders are off-limits even for reads.

Search is a stdlib scan: the vault is ~100 notes / <1MB of text, so scoring in
Python is instant and needs no ripgrep install.
# ponytail: linear scan, swap internals to ripgrep if the vault grows 100x
"""

import asyncio
import re
import subprocess
import time
from pathlib import Path
from urllib.parse import quote

from pydantic import BaseModel

from config.settings import get_settings

_SNIPPET_CHARS = 300
_NOTE_CHARS = 4000
_FILENAME_BONUS = 5
_STOPWORDS = frozenset(
    ["the", "and", "did", "was", "for", "you", "what", "that", "this", "with",
     "from", "have", "were", "when", "your", "about", "are", "how", "did"]
)


class VaultHit(BaseModel):
    path: str  # vault-relative
    snippet: str


def _root() -> Path:
    root = Path(get_settings().vault_path).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"VAULT_PATH is not a directory: {root}")
    return root


def _is_off_limits(rel: Path) -> bool:
    if any(part.startswith(".") for part in rel.parts):
        return True  # .obsidian, .git, dotfiles
    excludes = [e.strip().strip("/") for e in get_settings().vault_exclude.split(",") if e.strip()]
    return any(rel.is_relative_to(ex) for ex in excludes)


def _resolve(rel: str) -> Path:
    """Vault-relative path -> absolute. Raises ValueError on escape or off-limits."""
    root = _root()
    path = (root / rel).resolve()  # collapses .. and follows symlinks
    if not path.is_relative_to(root):
        raise ValueError(f"path escapes vault: {rel}")
    if _is_off_limits(path.relative_to(root)):
        raise ValueError(f"path is off-limits: {rel}")
    return path


def read_note(rel: str) -> str:
    path = _resolve(rel)
    if not path.is_file():
        raise ValueError(f"no such note: {rel}")
    return path.read_text(encoding="utf-8", errors="replace")[:_NOTE_CHARS]


def recent(limit: int = 6) -> list[str]:
    """The most recently edited note names — working memory for the HUD."""
    root = _root()
    notes = [p for p in root.rglob("*.md") if not _is_off_limits(p.relative_to(root))]
    notes.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [p.stem for p in notes[:limit]]


def open_in_obsidian(note: str = "", *, run=None) -> str:
    """Hand the vault to Obsidian itself — it browses and graphs notes far better
    than we ever will. Opens the whole vault, or one note by name. macOS `open`
    with an obsidian:// URL; no shell, so the name can't inject anything."""
    run = run or subprocess.run  # resolved at call time so tests can patch it
    vault = Path(get_settings().vault_path).expanduser().name
    if not vault:
        raise ValueError("VAULT_PATH is not set")
    url = f"obsidian://open?vault={quote(vault)}"
    note = note.strip()
    if note:
        url += f"&file={quote(note)}"
    result = run(["open", url], check=False, capture_output=True, text=True)
    if getattr(result, "returncode", 0) != 0:
        raise ValueError((getattr(result, "stderr", "") or "could not open Obsidian").strip())
    return f"Opening {note or vault} in Obsidian, sir."


async def search(query: str, max_hits: int = 5) -> list[VaultHit]:
    return await asyncio.to_thread(_search_sync, query, max_hits)


def _search_sync(query: str, max_hits: int) -> list[VaultHit]:
    root = _root()
    terms = [
        t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 2 and t not in _STOPWORDS
    ]
    if not terms:
        return []
    scored: list[tuple[int, str, str, str]] = []
    for path in root.rglob("*.md"):
        rel = path.relative_to(root)
        if _is_off_limits(rel) or not path.resolve().is_relative_to(root):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        low = text.lower()
        score = sum(low.count(t) for t in terms)
        score += _FILENAME_BONUS * sum(t in str(rel).lower() for t in terms)
        if score:
            scored.append((score, str(rel), text, low))
    scored.sort(key=lambda item: -item[0])
    hits = []
    for _, rel_str, text, low in scored[:max_hits]:
        first = min((i for i in (low.find(t) for t in terms) if i != -1), default=0)
        start = max(0, first - 80)
        hits.append(VaultHit(path=rel_str, snippet=text[start : start + _SNIPPET_CHARS]))
    return hits


def append_inbox(text: str) -> str:
    """Append a timestamped capture to _inbox/jarvis-notes.md. The ONLY vault write."""
    text = text.strip()
    if not text:
        raise ValueError("refusing to append an empty note")
    inbox = _root() / "_inbox"
    inbox.mkdir(exist_ok=True)
    target = inbox / "jarvis-notes.md"
    stamp = time.strftime("%Y-%m-%d %H:%M")  # local time — inbox notes read as sir wrote them
    with target.open("a", encoding="utf-8") as f:
        f.write(f"- {stamp} — {text}\n")
    return str(target.relative_to(_root()))
