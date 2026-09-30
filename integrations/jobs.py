"""jarvis-life-os · integrations/jobs.py

Jobs command center, READ side. The nightly job engine (Claude, in the cloud)
drops each batch into ~/Downloads/Jobs/<YYYY-MM-DD>/batch.json; sir's clicks
live in _engine/state/decisions_<batch>.json (written by jobs_actions.py) so the
next Claude run reads exactly what he decided. Pipeline totals come from the
vault tracker. Every read is cached by file mtime, so 5-second polling costs a
few stat() calls and nothing else.
"""

import json
import re
from collections import Counter
from pathlib import Path

from config.settings import get_settings

BATCH_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DECISIONS = ("approve", "skip", "")
ROLE_FIELDS = ("n", "key", "company", "role", "url", "apply_url", "ats", "submit_mode",
               "tier", "needs", "consents", "status", "portal", "folder")
_cache: dict[str, tuple[float, object]] = {}


def jobs_dir() -> Path:
    return Path(get_settings().jobs_dir).expanduser()


def state_dir() -> Path:
    return jobs_dir() / "_engine" / "state"


def _cached(path: Path, parse, default):
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return default
    hit = _cache.get(str(path))
    if hit and hit[0] == mtime:
        return hit[1]
    try:
        value = parse(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default
    _cache[str(path)] = (mtime, value)
    return value


def read_json(path: Path, default):
    return _cached(path, json.loads, default)


def check_batch(batch: str) -> str:
    batch = str(batch).strip()
    if not BATCH_RE.match(batch):
        raise ValueError("batch must look like YYYY-MM-DD")
    return batch


def batches() -> list[str]:
    root = jobs_dir()
    if not root.is_dir():
        return []
    names = [p.name for p in root.iterdir()
             if p.is_dir() and BATCH_RE.match(p.name) and (p / "batch.json").is_file()]
    return sorted(names, reverse=True)


def decisions_path(batch: str) -> Path:
    return state_dir() / f"decisions_{check_batch(batch)}.json"


def decisions(batch: str) -> dict:
    data = read_json(decisions_path(batch), {})
    return data if isinstance(data, dict) else {}


def _files(batch: str, folder: str) -> dict:
    base = jobs_dir() / batch / (folder or "_missing_")
    return {"resume": any(base.glob("*Resume.pdf")),
            "cover": any(base.glob("*CoverLetter.pdf")),
            "folder": base.is_dir()}


def roles(batch: str) -> list[dict]:
    batch = check_batch(batch)
    rows = read_json(jobs_dir() / batch / "batch.json", [])
    picked = decisions(batch)
    out = []
    for row in rows if isinstance(rows, list) else []:
        mine = picked.get(str(row.get("n")), {})
        item = {field: row.get(field) for field in ROLE_FIELDS}
        item["decision"] = mine.get("decision", "")
        item["answers"] = dict(mine.get("answers", {}))
        item["files"] = _files(batch, str(row.get("folder") or ""))
        out.append(item)
    return out


def progress(batch: str) -> dict:
    data = read_json(state_dir() / f"progress_{check_batch(batch)}.json", {})
    return data if isinstance(data, dict) else {}


def code_queue() -> list[dict]:
    data = read_json(state_dir() / "code_queue.json", [])
    return [e for e in data if isinstance(e, dict)] if isinstance(data, list) else []


def _tracker_rows(text: str) -> list[list[str]]:
    body = text.split("## Tracker", 1)[-1] if "## Tracker" in text else ""
    rows = []
    for line in body.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("|") and len(cells) >= 4 and not set(cells[0]) <= {"-", ":", " "}:
            rows.append(cells)
    return [r for r in rows if r[0].lower() != "company"]


def pipeline() -> dict:
    settings = get_settings()
    note = Path(settings.vault_path).expanduser() / settings.jobs_tracker_note
    rows = _cached(note, _tracker_rows, [])
    counts = Counter(r[3].lower() for r in rows)
    recent = [{"company": r[0], "role": r[1], "date": r[2], "status": r[3]} for r in rows[-8:]]
    return {"total": len(rows), "by_status": dict(counts), "recent": recent[::-1]}


def summarize(items: list[dict]) -> dict:
    return {
        "total": len(items),
        "by_tier": dict(Counter(i.get("tier") or "other" for i in items)),
        "by_mode": dict(Counter(i.get("submit_mode") or "claude" for i in items)),
        "needs_you": sum(1 for i in items if i.get("needs")),
        "approved": sum(1 for i in items if i["decision"] == "approve"),
        "skipped": sum(1 for i in items if i["decision"] == "skip"),
        "undecided": sum(1 for i in items if not i["decision"]),
    }


def overview() -> dict:
    all_batches = batches()
    latest = all_batches[0] if all_batches else ""
    items = roles(latest) if latest else []
    pending = [e for e in code_queue() if e.get("status") not in ("done", "failed")]
    return {
        "latest": latest,
        "batches": all_batches[:14],
        "summary": summarize(items),
        "progress": progress(latest) if latest else {},
        "code_queue": len(pending),
        "pipeline": pipeline(),
    }
