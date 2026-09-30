# Content Studio — Phase 7.5

Instagram + n8n as ONE section: n8n finds what's trending, you review on the
**Studio** screen (phone or Mac), edit the caption, two-tap **POST** — n8n
publishes to Instagram. Your IG credentials live in n8n on the VPS; the Mac
never holds a platform token. Every publish lands in the audit log.

```
n8n (trending scraper, IG creds)              Studio screen (/studio)
  /webhook/content-trending  ── pull ──►  review cards: score · hook · caption
  /webhook/content-publish   ◄─ post ──   two-tap POST ＋ / SKIP
```

## The two n8n workflows [LOHITH INPUT]

Both use the same `X-Friday-Secret` header-auth credential as docs/N8N-SETUP.md.

### 1. Trending pull — `CONTENT_TRENDING_WEBHOOK` (e.g. `/webhook/content-trending`)

POST, empty body in. **Respond to Webhook** with a JSON array:

```json
[
  {
    "id": "unique-stable-id",
    "title": "Before/after storefront reel",
    "hook": "POV: your shop at 6am vs 6pm",
    "source": "instagram",
    "url": "https://.../reel/...",
    "score": 91,
    "note": "trending audio: XYZ"
  }
]
```

`id` + `title` required; the rest optional. Re-sending the same `id` is safe —
reviewed items never resurface. Build it from whatever finds trends in your
niche: IG hashtag search, TikTok Creative Center, YouTube trending, an LLM
ranking step — the Studio doesn't care, it just wants the array.

### 2. Publish — `CONTENT_PUBLISH_WEBHOOK` (e.g. `/webhook/content-publish`)

Receives:

```json
{"id": "...", "title": "...", "url": "...", "source": "...", "caption": "edited caption"}
```

The workflow does the Instagram publish (Graph API content-publish, or queue it
into your scheduler) and responds with a short status text — it's shown in the
Studio and stored in the audit log.

## Arm it

`.env`:

```
CONTENT_TRENDING_WEBHOOK=/webhook/content-trending
CONTENT_PUBLISH_WEBHOOK=/webhook/content-publish
```

Restart the dashboard (`make dashboard` or the launchd agent). Until armed, the
Studio shows an honest empty state; a dead n8n degrades to "n8n unreachable,
sir" — never a hang. Items live in `data/content.db` (new → posted | skipped).
