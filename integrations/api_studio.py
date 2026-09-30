"""friday · integrations/api_studio.py

Content Studio endpoints (PARKED since 2026-09-28: no UI panel mounted, n8n
workflows archived). Kept so the future voice "make, caption, post with
approval" flow has its backend; the publish path still needs its two-step
confirm. Registered into the dashboard server's tables (jobs_api.py pattern).
"""

import asyncio

from integrations import content


def content_list(_body: dict) -> dict:
    return {
        "items": [item.model_dump() for item in content.items()],
        "armed": bool(content.get_settings().content_trending_webhook),
    }


def content_refresh(_body: dict) -> dict:
    pulled = asyncio.run(content.pull())
    return {"pulled": pulled, **content_list({})}


def content_publish(body: dict) -> dict:
    item_id = str(body.get("id", "")).strip()
    if not item_id:
        raise ValueError("missing item id")
    result = asyncio.run(content.publish(item_id, str(body.get("caption", ""))))
    return {"result": result, **content_list({})}


def content_skip(body: dict) -> dict:
    item_id = str(body.get("id", "")).strip()
    if not item_id:
        raise ValueError("missing item id")
    content.set_status(item_id, "skipped")
    return content_list({})


GET_API = {"/api/v1/studio/queue": content_list}
POST_API = {
    "/api/v1/studio/queue/refresh": content_refresh,
    "/api/v1/studio/publish": content_publish,
    "/api/v1/studio/skip": content_skip,
}
