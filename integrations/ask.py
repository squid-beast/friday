"""jarvis-life-os · integrations/ask.py

Text turns (phone PWA) into the SAME brain the voice uses: same router, same
confirm/PIN gates, same audit. Kill phrases are checked before the graph, so
"stand down" typed on the phone cuts the session at home. The graph runs on a
dedicated background event loop so the sync dashboard server can call it.
"""

import asyncio
import threading
from pathlib import Path
from typing import Any

from langgraph.types import Command

from brain.graph import get_brain
from client.local_intents import Intent, cut, match
from config.settings import get_settings

_TURN_TIMEOUT_S = 120


def _touch_stand_down() -> None:
    control = Path(get_settings().stand_down_file)
    control.parent.mkdir(parents=True, exist_ok=True)
    control.touch()


class BrainBridge:
    def __init__(self, brain_factory=get_brain, thread_id: str = "phone") -> None:
        self._factory = brain_factory
        self._config = {"configurable": {"thread_id": thread_id}}
        self._brain: Any = None
        self._pending_confirm = False
        self._lock = threading.Lock()  # one phone turn at a time
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._loop.run_forever, daemon=True).start()

    def _run(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(_TURN_TIMEOUT_S)

    def ask(self, text: str) -> dict:
        """One turn. Returns {"reply": str, "pending": bool} — pending means the
        brain asked a gate question and the NEXT text answers it."""
        text = text.strip()
        if not text:
            return {"reply": "Sir?", "pending": False}
        with self._lock:
            intent = match(text)
            if intent is Intent.STAND_DOWN:
                _touch_stand_down()
                self._pending_confirm = False
                return {"reply": "Standing down, sir.", "pending": False}
            if intent in (Intent.CAMERA_OFF, Intent.SCREEN_OFF, Intent.RESUME):
                return {"reply": cut(intent), "pending": False}
            if intent is Intent.MUTE:
                return {"reply": "Text is already quiet, sir.", "pending": False}
            if self._brain is None:
                self._brain = self._run(self._factory())
            if self._pending_confirm:
                self._pending_confirm = False
                payload: Any = Command(resume=text)
            else:
                payload = {"messages": [{"role": "user", "content": text}]}
            result = self._run(self._brain.ainvoke(payload, self._config))
            if result.get("__interrupt__"):
                self._pending_confirm = True
                return {
                    "reply": result["__interrupt__"][0].value["question"],
                    "pending": True,
                }
            return {"reply": result["reply"], "pending": False}
