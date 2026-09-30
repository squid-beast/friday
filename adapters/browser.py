"""friday · adapters/browser.py

Web hands via browser-use, ALWAYS in the dedicated Chrome profile
(~/friday-chrome) — never sir's own browser. Hard max-steps cap from settings.
The confirm gate lives in the vision node; by the time this runs, sir said yes.
Heavy imports are lazy so startup and the kill path never pay for them.
"""

from pathlib import Path

from config.settings import get_settings

_RESULT_CHARS = 500


async def run_task(task: str) -> str:
    from browser_use import Agent, BrowserProfile, ChatAnthropic  # lazy — seconds of import

    settings = get_settings()
    if not settings.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")
    profile = BrowserProfile(
        executable_path=settings.chrome_path,
        user_data_dir=str(Path(settings.browser_profile_dir).expanduser()),
        headless=False,  # sir watches his hands work
    )
    agent = Agent(
        task=task,
        llm=ChatAnthropic(model=settings.model_smart, api_key=settings.anthropic_api_key),
        browser_profile=profile,
    )
    history = await agent.run(max_steps=settings.browser_max_steps)
    result = history.final_result()
    return (result or "the task ended without a final report")[:_RESULT_CHARS]
