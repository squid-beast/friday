"""friday · tests/scenario/test_demo_script.py

L4: docs/DEMO-SCRIPT.md steps 2-7 as ONE continuous thread through the real
graph (fake adapters, real routing/gates/checkpointing). Steps 1 and 8 are
daemon-level and live in tests/unit/test_daemon.py; the offline-kill proof is
tests/unit/test_daemon_process.py. The demo is rehearsed by machine before it
is rehearsed by sir.
"""

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from adapters.screenpipe import ScreenHit
from adapters.vault import VaultHit
from audit.log import Event
from brain.graph import build_graph
from brain.nodes.memory_writer import drain
from config.tools import Tool
from tests.fakes import FakeLLM, FakeMemory, FakeVault

THREAD = {"configurable": {"thread_id": "demo"}}

PIPELINE = Tool(
    name="content_pipeline",
    description="runs the content pipeline for a new reel",
    adapter="adapters.n8n:call",
    webhook_path="/webhook/content",
    risk="confirm",
)


class DemoRig:
    """Fake world: vault note, screen history, camera sight, n8n executor, audit."""

    def __init__(self, llm: FakeLLM) -> None:
        self.executed: list[str] = []
        self.events: list[Event] = []
        self.memory = FakeMemory()
        vault = FakeVault(
            [VaultHit(path="projects/receivly.md", snippet="Quoted Receivly $1500 for setup.")]
        )

        async def execute(tool: Tool, utterance: str) -> str:
            self.executed.append(tool.name)
            return "pipeline started"

        async def screen_search(q: str, **kw):
            return [
                ScreenHit(
                    text="Stripe Pricing — 2.9% + 30c per transaction",
                    app="Safari", window="Stripe", timestamp="2026-08-09T16:10:00Z",
                )
            ]

        async def look(question: str) -> str:
            return "A ceramic coffee mug"

        def audit(tool: str, args: str, result: str, *, confirmed: bool) -> None:
            self.events.append(
                Event(ts=float(len(self.events)), kind="tool", detail=f"{tool}: {result}")
            )

        self.graph = build_graph(
            InMemorySaver(),
            think=llm.think,
            search=vault.search,
            recall=self.memory.recall,
            append=vault.append_inbox,
            remember=self.memory.remember,
            tools=lambda: [PIPELINE],
            execute=execute,
            audit=audit,
            audit_read=lambda: self.events,
            screen_search=screen_search,
            look=look,
            browse=None,
        )

    async def say(self, text: str) -> dict:
        result = await self.graph.ainvoke(
            {"messages": [{"role": "user", "content": text}]}, THREAD
        )
        await drain()
        return result


async def test_the_demo_steps_2_through_7() -> None:
    # Extraction (the 3rd call of a turn) fires ONLY on fact-hinting utterances
    # since the 2026-08-11 gate — in this demo that's step 3's "Remember: ..."
    llm = FakeLLM(
        [
            # 2 · vault question
            "vault", "Fifteen hundred dollars for the Receivly setup, sir.",
            # 3 · remember a fact (gate passes -> extraction call)
            "chat", "Noted, sir.", "Sir's demo day was today and it went clean",
            # 4 · ops with spoken confirm (router, select -> pause; then summary)
            "ops", "content_pipeline",
            "The content pipeline is running, sir.",
            # 5 · screen recall
            "recall", "The Stripe pricing page, sir — yesterday around four.",
            # 6 · camera
            "vision", "camera", "A ceramic coffee mug, sir — the lucky one.",
            # 7 · audit trail
            "ops",
            (
                "Today I answered from the vault, ran the content pipeline once, "
                "and took one look through the camera, sir."
            ),
        ]
    )
    rig = DemoRig(llm)

    # Step 2 — vault brain
    result = await rig.say("What did I quote the Receivly client last month?")
    assert result["reply"] == "Fifteen hundred dollars for the Receivly setup, sir."

    # Step 3 — memory write
    result = await rig.say("Remember: demo day was today and it went clean.")
    assert result["reply"] == "Noted, sir."
    assert rig.memory.stored == ["Sir's demo day was today and it went clean"]

    # Step 4 — ops + confirm gate
    result = await rig.graph.ainvoke(
        {"messages": [{"role": "user", "content": "Run my content pipeline."}]}, THREAD
    )
    assert rig.executed == []  # nothing before the spoken yes
    assert "Shall I proceed, sir?" in result["__interrupt__"][0].value["question"]
    result = await rig.graph.ainvoke(Command(resume="Yes."), THREAD)
    await drain()
    assert rig.executed == ["content_pipeline"]
    assert result["reply"] == "The content pipeline is running, sir."

    # Step 5 — screen recall
    result = await rig.say("What was that pricing page I looked at yesterday?")
    assert result["reply"] == "The Stripe pricing page, sir — yesterday around four."

    # Step 6 — camera on demand
    result = await rig.say("What am I holding?")
    assert result["reply"] == "A ceramic coffee mug, sir — the lucky one."

    # Step 7 — audit trail readback
    result = await rig.say("What did you do today?")
    assert "content pipeline" in result["reply"]
    kinds = [e.detail.split(":")[0] for e in rig.events]
    assert "content_pipeline" in kinds and "camera_look" in kinds

    # One continuous thread: the whole conversation is in state
    assert len(result["messages"]) == 12  # 6 exchanges x (user + assistant)
