"""friday · tests/scenario/test_demo_script.py

L4: docs/DEMO-SCRIPT.md steps 2-7 as ONE continuous thread through the real
graph (fake adapters, real routing/gates/checkpointing). Steps 1 and 8 are
daemon-level and live in tests/unit/test_daemon*.py; the offline-kill proof is
tests/unit/test_daemon_process.py. Redefined 2026-09-29 around what is linked:
vault, memory, weather, calendar booking (confirm gate), jobs status, Spotify.
"""

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from adapters.vault import VaultHit
from audit.log import Event
from brain.graph import build_graph
from brain.nodes.memory_writer import drain
from config.tools import load_tools
from tests.fakes import FakeLLM, FakeMemory, FakeVault

THREAD = {"configurable": {"thread_id": "demo"}}
RESULTS = {
    "weather": "Farmington Hills: 64°F, clear, 10% rain",
    "calendar_event": "booked: Lunch with Sam, tomorrow 12:00",
    "jobs_status": "latest batch 2026-09-28: 12 roles, 4 approved, 2 skipped, 6 undecided",
    "spotify_play": "playing: Die With A Smile",
}


class DemoRig:
    """Fake world: vault note, memory, the REAL tool registry with a fake executor."""

    def __init__(self, llm: FakeLLM) -> None:
        self.executed: list[str] = []
        self.events: list[Event] = []
        self.memory = FakeMemory()
        vault = FakeVault(
            [VaultHit(path="projects/receivly.md", snippet="Quoted Receivly $1500 for setup.")]
        )

        async def execute(tool, utterance: str) -> str:
            self.executed.append(tool.name)
            return RESULTS[tool.name]

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
            tools=load_tools,  # the real config/tools.yaml — the demo can't drift from it
            execute=execute,
            audit=audit,
            audit_read=lambda: self.events,
        )

    async def say(self, text: str) -> dict:
        result = await self.graph.ainvoke(
            {"messages": [{"role": "user", "content": text}]}, THREAD
        )
        await drain()
        return result


async def test_the_demo_steps_2_through_7() -> None:
    # Extraction (the 3rd call of a turn) fires ONLY on fact-hinting utterances
    # (memory_writer gate) — in this demo that's step 3's "Remember: ..."
    llm = FakeLLM(
        [
            # 2 · vault question
            "vault", "Fifteen hundred dollars for the Receivly setup, sir.",
            # 3 · remember a fact (gate passes -> extraction call)
            "chat", "Noted, sir.", "Sir's demo day was today and it went clean",
            # 4 · weather (safe tool: router, select, summary)
            "ops", "weather", "Sixty-four and clear, sir.",
            # 5 · calendar booking (confirm gate: router, select -> pause; summary)
            "ops", "calendar_event", "Lunch with Sam is on the books for noon, sir.",
            # 6 · jobs status
            "ops", "jobs_status", "Twelve roles in the latest batch, sir; six await you.",
            # 7 · Spotify
            "ops", "spotify_play", "Playing Die With A Smile, sir.",
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

    # Step 4 — weather
    result = await rig.say("What's the weather today?")
    assert result["reply"] == "Sixty-four and clear, sir."

    # Step 5 — calendar booking behind the spoken confirm gate
    result = await rig.graph.ainvoke(
        {"messages": [{"role": "user", "content": "Put lunch with Sam on my calendar "
                                                  "tomorrow at noon."}]}, THREAD
    )
    assert rig.executed == ["weather"]  # nothing booked before the spoken yes
    assert "Shall I proceed, sir?" in result["__interrupt__"][0].value["question"]
    result = await rig.graph.ainvoke(Command(resume="Yes."), THREAD)
    await drain()
    assert rig.executed == ["weather", "calendar_event"]
    assert result["reply"] == "Lunch with Sam is on the books for noon, sir."

    # Step 6 — jobs status
    result = await rig.say("How's my job search going?")
    assert result["reply"] == "Twelve roles in the latest batch, sir; six await you."

    # Step 7 — Spotify
    result = await rig.say("Play some music on Spotify.")
    assert result["reply"] == "Playing Die With A Smile, sir."
    assert rig.executed == ["weather", "calendar_event", "jobs_status", "spotify_play"]

    # One continuous thread: the whole conversation is in state
    assert len(result["messages"]) == 12  # 6 exchanges x (user + assistant)
