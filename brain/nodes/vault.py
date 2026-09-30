"""jarvis-life-os · brain/nodes/vault.py

Vault questions: search leos-brain + recall remembered facts -> synthesized
in-persona answer, grounded ONLY in that context. Note-taking phrases append to
the vault inbox instead (deterministic match, no LLM involved).
"""

import asyncio
import logging
import re

from adapters import memory as memory_adapter
from adapters import vault as vault_adapter
from adapters.llm import think as llm_think
from brain.nodes.chat import LLM_APOLOGY, persona
from brain.state import JarvisState, assistant_reply, last_user

log = logging.getLogger(__name__)

VAULT_APOLOGY = "Apologies, sir — I can't reach the vault right now."
NOTHING_FOUND = "I don't have anything on that in the vault, sir."
NOTED = "Noted, sir."
_NOTE_RE = re.compile(
    r"^(?:please\s+)?(?:take a note|note down|note that|write (?:this|that) down|"
    r"add to (?:my )?inbox|jot (?:this|that) down)\b[,:.!]?\s*(.*)$",
    re.IGNORECASE | re.DOTALL,
)

_PROMPT = """\
Answer sir's question using ONLY the context below, from his own vault and memory.
If the context does not contain the answer, say so plainly. Speak as Jarvis.

Question: {question}

Context:
{context}"""


async def vault_node(
    state: JarvisState,
    *,
    think=llm_think,
    search=vault_adapter.search,
    recall=memory_adapter.recall,
    append=vault_adapter.append_inbox,
) -> dict:
    utterance = last_user(state.messages)
    note = _NOTE_RE.match(utterance.strip())
    if note:
        content = note.group(1).strip()
        if not content:
            return assistant_reply("What shall I note down, sir?")
        try:
            await asyncio.to_thread(append, content)
        except Exception:
            log.warning("inbox append failed", exc_info=True)
            return assistant_reply(VAULT_APOLOGY)
        return assistant_reply(NOTED)

    hits = facts = None
    try:
        hits = await search(utterance)
    except Exception:
        log.warning("vault search failed", exc_info=True)
    try:
        facts = await recall(utterance)
    except Exception:
        log.warning("memory recall failed", exc_info=True)
    if hits is None and facts is None:
        return assistant_reply(VAULT_APOLOGY)
    if not hits and not facts:
        return assistant_reply(NOTHING_FOUND)

    context = "\n".join(
        [f"[note: {h.path}]\n{h.snippet}" for h in hits or []]
        + [f"[remembered] {f}" for f in facts or []]
    )
    try:
        reply = (
            await think(_PROMPT.format(question=utterance, context=context), system=persona())
        ).strip()
    except Exception:
        log.warning("vault synthesis failed", exc_info=True)
        reply = LLM_APOLOGY
    return assistant_reply(reply)
