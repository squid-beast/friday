"""jarvis-life-os · config/tools.py

Typed loader for config/tools.yaml — the ONLY place capabilities are declared
(CONVENTIONS.md). A bad entry fails loudly at load, not silently at 2am.
"""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel

_TOOLS_PATH = Path(__file__).resolve().parent / "tools.yaml"


class Tool(BaseModel):
    name: str
    description: str  # the router and the ops selector read this
    adapter: str  # "module.path:function"
    webhook_path: str = ""  # n8n tools only
    risk: Literal["safe", "confirm", "pin", "blocked"]  # pin = confirm + spoken 4-digit PIN


def load_tools(path: Path = _TOOLS_PATH) -> list[Tool]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [Tool(**entry) for entry in (data.get("tools") or [])]
