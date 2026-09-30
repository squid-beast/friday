"""friday · adapters/mac_actions.py

"Open Slack" / "search YouTube for lo-fi beats" — tool `open_and_search`.
Apps: the spoken name is matched against what is ACTUALLY installed
(/Applications, /System/Applications, ~/Applications) and opened with
`open -a <exact bundle name>`; an unknown name is refused, never guessed.
Searches: the query is URL-encoded into a fixed template and opened in the
default browser. Subprocess with an argument list — no shell, no injection.
"""

import asyncio
import re
import subprocess
from pathlib import Path
from urllib.parse import quote_plus

_APP_DIRS = (Path("/Applications"), Path("/System/Applications"),
             Path("/System/Applications/Utilities"), Path.home() / "Applications")
_SITES = {
    "google": "https://www.google.com/search?q={}",
    "youtube": "https://www.youtube.com/results?search_query={}",
    "github": "https://github.com/search?q={}",
    "amazon": "https://www.amazon.com/s?k={}",
    "maps": "https://www.google.com/maps/search/{}",
    "wikipedia": "https://en.wikipedia.org/w/index.php?search={}",
}
_SITE_WORDS = "|".join(_SITES)
_SEARCH = [
    re.compile(rf"\b(?:search|look up|find)\s+(?:on\s+)?({_SITE_WORDS})\s+for\s+(.+)", re.I),
    re.compile(rf"\b(?:search(?: for)?|look up|find)\s+(.+?)\s+on\s+({_SITE_WORDS})\b", re.I),
    re.compile(r"\b(google)\s+(.+)", re.I),
    re.compile(r"\b(?:search(?: the web)?(?: for)?|look up)\s+(.+)", re.I),
]
_OPEN = re.compile(r"\b(?:open|launch|start)\s+(?:up\s+)?(?:the\s+|my\s+)?(.+?)(?:\s+app)?[.!?]*$",
                   re.I)


def installed_apps(dirs=_APP_DIRS) -> dict[str, str]:
    """lowercased name -> exact bundle name, for every installed .app."""
    apps = {}
    for d in dirs:
        for app in d.glob("*.app") if d.is_dir() else ():
            apps[app.stem.lower()] = app.stem
    return apps


def resolve_app(spoken: str, apps: dict[str, str]) -> str | None:
    name = spoken.strip().lower()
    if name in apps:
        return apps[name]
    matches = [exact for low, exact in apps.items() if low.startswith(name) or name in low.split()]
    return matches[0] if len(matches) == 1 else None  # ambiguous -> refuse, never guess


def search_url(utterance: str) -> str | None:
    for i, rx in enumerate(_SEARCH):
        if m := rx.search(utterance):
            if i == 0:
                site, query = m.group(1), m.group(2)
            elif i == 1:
                query, site = m.group(1), m.group(2)
            elif i == 2:
                site, query = "google", m.group(2)
            else:
                site, query = "google", m.group(1)
            return _SITES[site.lower()].format(quote_plus(query.strip().rstrip(".?!")))
    return None


def _open(args: list[str], run=subprocess.run) -> bool:
    return run(["open", *args], check=False, capture_output=True, text=True).returncode == 0


async def open_or_search(_arg: str, utterance: str, *, run=subprocess.run,
                         apps=installed_apps) -> str:
    url = search_url(utterance)
    if url:
        ok = await asyncio.to_thread(_open, [url], run)
        return f"opened the search: {url}" if ok else "the browser wouldn't open the search"
    m = _OPEN.search(utterance)
    if not m:
        return "tell me an app to open or something to search for"
    app = resolve_app(m.group(1), await asyncio.to_thread(apps))
    if app is None:
        return f"I can't find an installed app called '{m.group(1).strip()}'"
    ok = await asyncio.to_thread(_open, ["-a", app], run)
    return f"opened {app}" if ok else f"{app} wouldn't open"
