"""friday · tests/evals/test_tool_eval.py

L3 tool-selection eval: every case in tool_cases.yaml runs through the real
ops_select node (real Haiku, real config/tools.yaml) and must pick the expected
tool — or none. >= 90% to pass; every registered tool must be covered.
"""

import asyncio
from pathlib import Path

import pytest
import yaml

from brain.nodes.ops import ops_select_node
from brain.state import FridayState
from config.settings import get_settings
from config.tools import load_tools

_CASES_PATH = Path(__file__).with_name("tool_cases.yaml")
_PASS_RATE = 0.90

pytestmark = pytest.mark.skipif(
    not get_settings().anthropic_api_key, reason="ANTHROPIC_API_KEY not set — eval needs the API"
)


def _cases() -> list[dict]:
    return yaml.safe_load(_CASES_PATH.read_text(encoding="utf-8"))["cases"]


def test_every_registered_tool_has_a_case() -> None:
    covered = {c["expect"] for c in _cases()}
    assert {t.name for t in load_tools()} <= covered


async def test_tool_selection_at_least_90_percent() -> None:
    cases = _cases()

    async def select(case: dict) -> tuple[dict, str]:
        state = FridayState(messages=[{"role": "user", "content": case["utterance"]}])
        return case, (await ops_select_node(state)).get("pending_tool", "")

    results = await asyncio.gather(*(select(c) for c in cases))
    misses = [(c["utterance"], c["expect"], got) for c, got in results if got != c["expect"]]
    accuracy = 1 - len(misses) / len(cases)
    detail = "\n".join(f"  {u!r}: expected {e!r}, got {g!r}" for u, e, g in misses)
    assert accuracy >= _PASS_RATE, f"tool accuracy {accuracy:.0%} < 90%\n{detail}"
