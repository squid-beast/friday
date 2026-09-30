"""friday · tests/unit/test_router.py

Router node with FakeLLM: our parsing/fallback logic, not the model.
Real-model accuracy lives in tests/evals/test_router_eval.py.
"""

from pathlib import Path

import pytest

import brain.nodes.router as router_mod
from brain.nodes.router import route_node
from brain.state import FridayState
from tests.fakes import BrokenLLM, FakeLLM


def _state(utterance: str) -> FridayState:
    return FridayState(messages=[{"role": "user", "content": utterance}])


async def test_clean_answer_routes() -> None:
    llm = FakeLLM(["vault"])
    assert await route_node(_state("what did I quote Receivly?"), think=llm.think) == {
        "route": "vault"
    }
    assert llm.calls[0]["fast"] is True  # routing always uses the cheap model


async def test_noisy_answer_still_parsed() -> None:
    llm = FakeLLM(["Route: VAULT."])
    assert (await route_node(_state("my notes?"), think=llm.think))["route"] == "vault"


async def test_garbage_answer_falls_back_to_chat() -> None:
    llm = FakeLLM(["hmm, unsure entirely"])
    assert (await route_node(_state("hello"), think=llm.think))["route"] == "chat"


async def test_llm_failure_falls_back_to_chat() -> None:
    assert (await route_node(_state("hello"), think=BrokenLLM().think))["route"] == "chat"


async def test_no_user_message_skips_llm() -> None:
    llm = FakeLLM([])
    assert (await route_node(FridayState(), think=llm.think))["route"] == "chat"
    assert llm.calls == []


async def test_prompt_carries_utterance_and_registered_tools(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tools = tmp_path / "tools.yaml"
    tools.write_text(
        "tools:\n  - name: content_pipeline\n"
        "    description: runs the content pipeline for a new reel\n"
    )
    monkeypatch.setattr(router_mod, "_TOOLS_PATH", tools)
    llm = FakeLLM(["ops"])
    await route_node(_state("run my content pipeline"), think=llm.think)
    prompt = llm.calls[0]["prompt"]
    assert "run my content pipeline" in prompt
    assert "content_pipeline: runs the content pipeline" in prompt


async def test_empty_tools_yaml_is_fine() -> None:
    llm = FakeLLM(["chat"])
    await route_node(_state("good morning"), think=llm.think)
    assert "ops — DO a concrete action" in llm.calls[0]["prompt"]


async def test_router_caps_output_tokens() -> None:
    llm = FakeLLM(["chat"])
    await route_node(_state("hello"), think=llm.think)
    assert llm.calls[0]["max_tokens"] == 16  # one-word answer, never pay for more


async def test_echoed_tool_name_routes_to_ops() -> None:
    """Haiku sometimes answers with the TOOL name instead of a route word
    ("open_obsidian"); that is an ops request, not a fallback to chat."""
    for raw in ("open_obsidian", "jobs_status", "Route: spotify_play"):
        llm = FakeLLM([raw])
        assert (await route_node(_state("open my notes"), think=llm.think))["route"] == "ops", raw


async def test_recall_is_still_a_route_so_it_can_answer_honestly() -> None:
    llm = FakeLLM(["recall"])
    out = await route_node(_state("what was that page I saw yesterday?"), think=llm.think)
    assert out["route"] == "recall"  # graph lands it on `unarmed`: sense switched off
