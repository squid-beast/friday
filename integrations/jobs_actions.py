"""friday · integrations/jobs_actions.py

Jobs command center, WRITE side. Sir's clicks become one small JSON file per
batch (_engine/state/decisions_<batch>.json): approve / skip per role, plus his
answers to the "needs you" questions. Writes are atomic (temp file + rename) so
a Claude run reading mid-click never sees half a file. Every change is audited.
Opening a resume or letter hands the PDF to macOS Preview — only paths inside
the jobs folder, never a shell.
"""

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

from audit.log import log_tool
from integrations import jobs

MAX_ANSWER = 2000
OPENABLE = {"resume": "*Resume.pdf", "cover": "*CoverLetter.pdf", "folder": ""}


def _role(batch: str, n: int) -> dict:
    for item in jobs.roles(batch):
        if item.get("n") == n:
            return item
    raise ValueError(f"no role #{n} in batch {batch}")


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".decisions-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


def _update(batch: str, n: int, change) -> dict:
    batch = jobs.check_batch(batch)
    _role(batch, n)
    path = jobs.decisions_path(batch)
    data = {k: dict(v) for k, v in jobs.decisions(batch).items() if isinstance(v, dict)}
    entry = data.setdefault(str(n), {})
    change(entry)
    entry["ts"] = time.time()
    _write(path, data)
    return entry


def decide(batch: str, n: int, decision: str) -> dict:
    if decision not in jobs.DECISIONS:
        raise ValueError("decision must be approve, skip or empty")

    def change(entry: dict) -> None:
        entry["decision"] = decision

    entry = _update(batch, n, change)
    log_tool("jobs.decide", f"{batch} #{n}", decision or "cleared", confirmed=True)
    return entry


def answer(batch: str, n: int, question: str, text: str) -> dict:
    question, text = question.strip(), text.strip()
    if not question:
        raise ValueError("missing question")
    if len(text) > MAX_ANSWER:
        raise ValueError(f"answer longer than {MAX_ANSWER} characters")

    def change(entry: dict) -> None:
        answers = dict(entry.get("answers", {}))
        if text:
            answers[question] = text
        else:
            answers.pop(question, None)
        entry["answers"] = answers

    entry = _update(batch, n, change)
    log_tool("jobs.answer", f"{batch} #{n}", "saved" if text else "cleared", confirmed=True)
    return entry


def open_file(batch: str, n: int, which: str, *, run=None) -> str:
    """Bring a role's resume, cover letter or folder onto sir's screen."""
    if which not in OPENABLE:
        raise ValueError("which must be resume, cover or folder")
    batch = jobs.check_batch(batch)
    folder = str(_role(batch, n).get("folder") or "")
    root = jobs.jobs_dir().resolve()
    base = (root / batch / folder).resolve()
    if not folder or root not in base.parents or not base.is_dir():
        raise ValueError("that role's folder isn't on this Mac")
    target = base if which == "folder" else next(iter(sorted(base.glob(OPENABLE[which]))), None)
    if target is None:
        raise ValueError(f"no {which} file for #{n}")
    run = run or subprocess.run
    result = run(["open", str(target)], check=False, capture_output=True, text=True)
    if getattr(result, "returncode", 0) != 0:
        raise ValueError((getattr(result, "stderr", "") or "could not open it").strip())
    log_tool("jobs.open", f"{batch} #{n} {which}", "opened", confirmed=True)
    return f"Opened the {which} for #{n}."
