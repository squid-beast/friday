"""friday · integrations/metrics_voice.py

The Mission Board, read aloud — tools.yaml entry `metrics_report`. Builds a
deterministic factual digest from the store (no LLM here: the ops node's
summary step turns it into persona speech, one model call total). If the
utterance names a platform, only that platform is read back.
"""

from integrations import store

_KEYWORDS = {
    "instagram": ("instagram", "insta", "reel", "reels", "ig"),
    "bookyourslot": ("bookyourslot", "booking", "bookings", "revenue", "mrr"),
    "leads": ("lead", "leads", "converted", "follow-up", "followup"),
    "n8n": ("n8n", "workflow", "workflows", "automation"),
    "friday": ("friday", "yourself", "your own"),
}


def _wanted(utterance: str, platforms: list[str]) -> list[str]:
    low = utterance.lower()
    hits = [p for p in platforms if any(k in low for k in _KEYWORDS.get(p, (p,)))]
    return hits or platforms  # no platform named -> the whole board


async def report(_arg: str, utterance: str) -> str:
    data = store.summary(days=7)
    if not data:
        return "the metrics store is empty — no collection has run yet"
    lines = []
    for platform in _wanted(utterance, sorted(data)):
        for metric, points in data[platform].items():
            latest = points[-1].value
            delta = latest - points[-2].value if len(points) > 1 else 0.0
            arrow = "up" if delta > 0 else "down" if delta < 0 else "flat"
            lines.append(
                f"{platform} {metric}: {latest:g} ({arrow} {abs(delta):g} vs previous)"
            )
    return "; ".join(lines)
