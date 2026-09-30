"""friday · integrations/jobs_voice.py

The Jobs command center, read aloud — tools.yaml entry `jobs_status`. A
deterministic digest of the latest batch, sir's decisions, and the tracker
pipeline (no LLM here: the ops summary step speaks it in persona). Bounded by a
timeout because a macOS-blocked ~/Downloads read would otherwise hang the turn.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor

from integrations import jobs

_TIMEOUT_S = 5.0
# ponytail: one dedicated thread — a TCC-blocked read can only ever pin THIS thread,
# never leak workers from asyncio's shared default pool; a stuck read = later asks time out.
_POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix="jobs-voice")


def _digest(ov: dict) -> str:
    if not ov["latest"]:
        return "no job batches yet — the job engine hasn't dropped one in the Jobs folder"
    s = ov["summary"]
    parts = [
        f"latest batch {ov['latest']}: {s['total']} roles, {s['approved']} approved, "
        f"{s['skipped']} skipped, {s['undecided']} undecided",
    ]
    if s["needs_you"]:
        parts.append(f"{s['needs_you']} need your answers")
    if ov["code_queue"]:
        parts.append(f"{ov['code_queue']} queued for submission")
    pipe = ov["pipeline"]
    if pipe["total"]:
        statuses = ", ".join(f"{n} {k}" for k, n in sorted(pipe["by_status"].items()))
        parts.append(f"tracker: {pipe['total']} applications ({statuses})")
    return "; ".join(parts)


async def status(_arg: str, _utterance: str) -> str:
    try:
        loop = asyncio.get_running_loop()
        ov = await asyncio.wait_for(loop.run_in_executor(_POOL, jobs.overview), _TIMEOUT_S)
    except TimeoutError:
        return "the Jobs folder didn't answer in time — macOS may be blocking ~/Downloads"
    except Exception as exc:  # any read failure becomes a spoken fact, never a crash
        return f"the jobs data isn't readable right now ({type(exc).__name__})"
    return _digest(ov)
