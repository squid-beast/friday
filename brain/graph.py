"""friday · brain/graph.py

The brain: router -> chat | vault | ops_select(->ops_execute) |
vision_select(->vision_execute) -> memory_writer -> END. The recall node
(screen memory) stays wired but DISARMED since screenpipe's removal
(2026-09-29): a "recall" route lands on `unarmed`.
New tools are registered in config/tools.yaml, NEVER by editing this wiring
(CONVENTIONS.md).

build_graph() takes fake adapters for tests; get_brain() is the production
graph with the SQLite checkpointer under data/ (+ optional LangSmith tracing).
"""

import os
from functools import partial
from pathlib import Path

import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph

from brain.nodes.chat import chat_node
from brain.nodes.memory_writer import memory_writer_node
from brain.nodes.ops import ops_execute_node, ops_select_node
from brain.nodes.router import route_node
from brain.nodes.vault import vault_node
from brain.nodes.vision import recall_node, vision_execute_node, vision_select_node
from brain.state import FridayState, assistant_reply
from config.settings import get_settings

UNARMED_REPLY = "That system isn't armed yet, sir."
ARMED = frozenset({"chat", "vault", "ops", "vision"})  # recall disarmed with screenpipe


async def _unarmed_node(state: FridayState) -> dict:
    return assistant_reply(UNARMED_REPLY)


def _pick(state: FridayState) -> str:
    return state.route if state.route in ARMED else "unarmed"


def _bind(fn, **deps):
    provided = {k: v for k, v in deps.items() if v is not None}
    return partial(fn, **provided) if provided else fn


def build_graph(
    checkpointer=None,
    *,
    think=None,
    stream=None,
    search=None,
    recall=None,
    append=None,
    remember=None,
    tools=None,
    execute=None,
    confirm=None,
    pin_check=None,
    audit=None,
    audit_read=None,
    screen_search=None,
    look=None,
    browse=None,
):
    """Compile the brain. Dep kwargs default to the real adapters; pass fakes in tests."""
    graph = StateGraph(FridayState)
    graph.add_node("router", _bind(route_node, think=think))
    graph.add_node("chat", _bind(chat_node, think=think, stream=stream))
    graph.add_node(
        "vault", _bind(vault_node, think=think, search=search, recall=recall, append=append)
    )
    graph.add_node(
        "ops_select", _bind(ops_select_node, think=think, tools=tools, audit_read=audit_read)
    )
    graph.add_node(
        "ops_execute",
        _bind(
            ops_execute_node,
            think=think,
            tools=tools,
            execute=execute,
            confirm=confirm,
            pin_check=pin_check,
            audit=audit,
        ),
    )
    graph.add_node("recall", _bind(recall_node, think=think, screen_search=screen_search))
    graph.add_node("vision_select", _bind(vision_select_node, think=think))
    graph.add_node(
        "vision_execute",
        _bind(
            vision_execute_node,
            think=think,
            look=look,
            browse=browse,
            confirm=confirm,
            audit=audit,
        ),
    )
    graph.add_node("unarmed", _unarmed_node)
    graph.add_node("memory_writer", _bind(memory_writer_node, think=think, remember=remember))
    graph.add_edge(START, "router")
    graph.add_conditional_edges(
        "router",
        _pick,
        {
            "chat": "chat",
            "vault": "vault",
            "ops": "ops_select",
            "vision": "vision_select",
            "recall": "recall",
            "unarmed": "unarmed",
        },
    )
    graph.add_conditional_edges(
        "ops_select",
        lambda s: "ops_execute" if s.pending_tool else "memory_writer",
        {"ops_execute": "ops_execute", "memory_writer": "memory_writer"},
    )
    graph.add_conditional_edges(
        "vision_select",
        lambda s: "vision_execute" if s.pending_action else "memory_writer",
        {"vision_execute": "vision_execute", "memory_writer": "memory_writer"},
    )
    for node in ("chat", "vault", "ops_execute", "vision_execute", "recall", "unarmed"):
        graph.add_edge(node, "memory_writer")
    graph.add_edge("memory_writer", END)
    return graph.compile(checkpointer=checkpointer)


def _arm_tracing() -> None:
    """LangSmith is opt-in: no key, no env mutation, no tracing (PLAN §5 P6)."""
    settings = get_settings()
    if settings.langsmith_api_key:
        os.environ.setdefault("LANGSMITH_TRACING", "true")
        os.environ.setdefault("LANGSMITH_API_KEY", settings.langsmith_api_key)
        os.environ.setdefault("LANGSMITH_PROJECT", settings.langsmith_project)


async def get_brain(db_path: str | None = None):
    """Production graph: real adapters, SQLite-checkpointed conversation state."""
    _arm_tracing()
    db_path = db_path or get_settings().checkpoint_db_path
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(db_path)
    return build_graph(AsyncSqliteSaver(conn))
