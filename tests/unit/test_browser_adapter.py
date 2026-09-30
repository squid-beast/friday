"""friday · tests/unit/test_browser_adapter.py

adapters/browser.py with browser_use mocked at import time: dedicated profile,
max-steps cap, missing key refusal. The live browser is acceptance-tested.
"""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.browser import run_task
from config.settings import get_settings


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("BROWSER_PROFILE_DIR", "~/friday-chrome")
    monkeypatch.setenv("BROWSER_MAX_STEPS", "7")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def fake_browser_use(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    history = MagicMock()
    history.final_result.return_value = "Booked the slot."
    agent = MagicMock()
    agent.run = AsyncMock(return_value=history)
    module = SimpleNamespace(
        Agent=MagicMock(return_value=agent),
        BrowserProfile=MagicMock(),
        ChatAnthropic=MagicMock(),
        _agent=agent,
    )
    monkeypatch.setitem(sys.modules, "browser_use", module)
    return module


async def test_runs_in_dedicated_profile_with_step_cap(fake_browser_use) -> None:
    result = await run_task("book the 9am slot")
    assert result == "Booked the slot."
    profile_kwargs = fake_browser_use.BrowserProfile.call_args.kwargs
    assert profile_kwargs["user_data_dir"] == str(Path("~/friday-chrome").expanduser())
    assert "Google Chrome" in profile_kwargs["executable_path"]
    assert fake_browser_use._agent.run.call_args.kwargs["max_steps"] == 7
    agent_kwargs = fake_browser_use.Agent.call_args.kwargs
    assert agent_kwargs["task"] == "book the 9am slot"


async def test_empty_final_result_still_reports(fake_browser_use) -> None:
    fake_browser_use._agent.run.return_value.final_result.return_value = None
    assert "without a final report" in await run_task("do something")


async def test_missing_key_refuses_before_launching(
    fake_browser_use, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    get_settings.cache_clear()
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        await run_task("anything")
    fake_browser_use.Agent.assert_not_called()
