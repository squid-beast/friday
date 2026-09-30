"""friday · adapters/vault_plan.py

Today's plan, kept in sir's own Obsidian daily note — `daily/<current year>/YYYY-MM-DD.md`
under a "## Friday plan" heading of checkboxes. (The vault's .obsidian/daily-notes.json
hard-codes the folder "daily/2026"; Friday follows the year, so next January also update
Obsidian's Daily Notes folder to daily/2027 to keep both writing the same note.)
The SECOND and last vault write path (after append_inbox): it goes through
vault._resolve, so escapes and off-limits folders are refused exactly as for
reads. Tool: `today_plan`.
"""

import asyncio
import re
import time

from adapters import vault

HEADING = "## Friday plan"
_ADD = re.compile(r"\b(?:add|put|include)\s+(.+?)\s+(?:to|on|in(?:to)?)\s+"
                  r"(?:today'?s|my|the|tonight'?s)\s+(?:plan|list|to-?do(?: list)?)\b", re.I)
_BOX = re.compile(r"^- \[( |x|X)\] (.+)$")


def _note_rel(now: float | None = None) -> str:
    t = time.localtime(now)
    return f"daily/{t.tm_year}/{time.strftime('%Y-%m-%d', t)}.md"


def items(now: float | None = None) -> list[tuple[bool, str]]:
    path = vault._resolve(_note_rel(now))
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    if HEADING not in lines:
        return []
    out = []
    for line in lines[lines.index(HEADING) + 1:]:
        if line.startswith("## "):
            break
        if m := _BOX.match(line.strip()):
            out.append((m.group(1).lower() == "x", m.group(2).strip()))
    return out


def add(item: str, now: float | None = None) -> str:
    item = item.strip().rstrip(".")
    if not item:
        raise ValueError("refusing to add an empty plan item")
    rel = _note_rel(now)
    path = vault._resolve(rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else [
        f"# {time.strftime('%Y-%m-%d', time.localtime(now))}"]
    if HEADING not in lines:
        lines += ["", HEADING]
    end = lines.index(HEADING) + 1
    while end < len(lines) and not lines[end].startswith("## "):
        end += 1
    while end > 0 and not lines[end - 1].strip():  # insert right after the last item
        end -= 1
    lines.insert(end, f"- [ ] {item}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return rel


async def plan(_arg: str, utterance: str) -> str:
    """"add X to today's plan" -> writes it; anything else reads the plan back."""
    try:
        if m := _ADD.search(utterance):
            rel = await asyncio.to_thread(add, m.group(1))
            return f"added '{m.group(1).strip()}' to today's plan ({rel})"
        todo = await asyncio.to_thread(items)
    except ValueError as exc:
        return f"the plan note isn't reachable: {exc}"
    if not todo:
        return "today's plan is empty — nothing added yet"
    open_items = [text for done, text in todo if not done]
    done = len(todo) - len(open_items)
    listed = "; ".join(open_items) if open_items else "everything is ticked off"
    return f"today's plan ({len(todo)} items, {done} done): {listed}"
