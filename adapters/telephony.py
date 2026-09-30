"""friday · adapters/telephony.py

Friday places a real phone call in sir's stead (risk=pin). Provider-agnostic
shell: it REFUSES cleanly until a provider + key are configured, and dispatches
once they are. Turn-key path is Vapi (an AI assistant dials and talks); Twilio
is left as a documented seam. What to sign up for → docs/CALLS.md.

Nothing here is half-working: unconfigured = a spoken refusal, never a dead call.
"""

import json
import logging
import re
import urllib.request

from config.settings import get_settings

log = logging.getLogger(__name__)

_VAPI_URL = "https://api.vapi.ai/call"  # confirm in docs/CALLS.md before first use
# E.164-ish: an optional + and 7 to 15 digits, ignoring spaces/dashes in the source.
_NUMBER = re.compile(r"\+?\d[\d\s\-()]{6,}\d")


def _extract_number(arg: str, utterance: str) -> str:
    m = _NUMBER.search(arg) or _NUMBER.search(utterance)
    return re.sub(r"[\s\-()]", "", m.group()) if m else ""


def _place_vapi(settings, to_number: str, goal: str) -> str:
    body = json.dumps(
        {
            "assistantId": settings.telephony_agent_id,
            "phoneNumberId": settings.telephony_from_number,
            "customer": {"number": to_number},
            "assistantOverrides": {"variableValues": {"goal": goal}},
        }
    ).encode()
    req = urllib.request.Request(
        _VAPI_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {settings.telephony_api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        resp.read()
    return f"Placing the call to {to_number} now, sir."


async def call(arg: str, utterance: str) -> str:
    """make_call tool. arg = optional number/context from tools.yaml; utterance = spoken ask."""
    settings = get_settings()
    if not settings.telephony_provider or not settings.telephony_api_key:
        return "I can't place calls yet, sir — telephony isn't set up. See docs/CALLS.md."
    number = _extract_number(arg, utterance)
    if not number:
        return "I'll need the number to dial, sir."
    if settings.telephony_provider != "vapi":
        return f"The {settings.telephony_provider} calling path isn't wired yet, sir."
    try:
        return _place_vapi(settings, number, utterance)
    except Exception:
        log.warning("call placement failed", exc_info=True)
        return "The call wouldn't connect, sir — I've noted it."
