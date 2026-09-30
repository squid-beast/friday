"""friday · tests/evals/test_router_eval.py

L3 eval: the REAL fast model against router_cases.yaml. Scored, not asserted
per-case — PASS is >= 90% overall. Needs ANTHROPIC_API_KEY; skipped without it
(make eval runs this; it is not part of make test-unit).
"""

import asyncio
from pathlib import Path

import pytest
import yaml

from brain.nodes.router import route_node
from brain.state import FridayState
from config.settings import get_settings

_CASES_PATH = Path(__file__).parent / "router_cases.yaml"
_PASS_RATE = 0.9
_MIN_CASES = 30  # Phase 6 floor (PLAN §5 P6)

pytestmark = pytest.mark.skipif(
    not get_settings().anthropic_api_key, reason="ANTHROPIC_API_KEY not set — eval needs the API"
)


def _cases() -> list[dict]:
    return yaml.safe_load(_CASES_PATH.read_text(encoding="utf-8"))["cases"]


def test_case_set_size_floor() -> None:
    assert len(_cases()) >= _MIN_CASES


async def test_router_accuracy_at_least_90_percent() -> None:
    cases = _cases()

    async def classify(case: dict) -> tuple[dict, str]:
        state = FridayState(messages=[{"role": "user", "content": case["utterance"]}])
        return case, (await route_node(state))["route"]

    results = await asyncio.gather(*(classify(c) for c in cases))
    misses = [(c["utterance"], c["expect"], got) for c, got in results if got != c["expect"]]
    accuracy = 1 - len(misses) / len(cases)
    detail = "\n".join(f"  {u!r}: expected {e}, got {g}" for u, e, g in misses)
    assert accuracy >= _PASS_RATE, f"router accuracy {accuracy:.0%} < 90%\n{detail}"
