# n8n setup — authed webhooks for Friday (Phase 4)

Friday calls your Hostinger n8n over HTTPS with a shared-secret header.
Five steps, once.

## 1. Generate the shared secret (on the Mac)

```bash
openssl rand -hex 32
```

Put it in `.env` along with your n8n URL:

```
N8N_BASE_URL=https://<your-n8n-domain>
N8N_WEBHOOK_SECRET=<the hex string>
```

## 2. Add header auth to each workflow's Webhook node (in n8n)

For each of the 5 workflows:

1. Open the workflow → its **Webhook** trigger node.
2. **Authentication** → `Header Auth`.
3. Create one shared credential (once, reused by all 5):
   - Name: `X-Friday-Secret`
   - Value: the same hex string as `.env`
4. Note the **Production URL path** (e.g. `/webhook/content-pipeline`) —
   that's the `webhook_path` for `config/tools.yaml`.
5. HTTP Method: `POST`. Activate the workflow (production, not test).

## 3. Register the workflows in config/tools.yaml

Uncomment and fill the template block in `config/tools.yaml`: name (spoken,
snake_case), description (the router matches your phrasing against this — write
it the way you'd say it), `webhook_path`, and risk:

- `safe` — read-only reports; runs immediately.
- `confirm` — anything that sends/changes things; Friday asks
  "Shall I proceed, sir?" and executes ONLY on an explicit yes.
- `blocked` — registered but refused until you change your mind.

## 4. Test one webhook from the Mac

```bash
curl -s -X POST "$N8N_BASE_URL/webhook/<path>" -H "X-Friday-Secret: <the hex string>" -d '{}'
```

Expect your workflow's response. A 403 means the credential doesn't match .env.

## 5. Talk to it

`make voice` → "run my content pipeline" → "Shall I proceed, sir?" → "yes".
Then "what did you do today?" — the execution is in the audit log.

Notes: Friday retries a failed call exactly once (transport/5xx only), times
out at 10s, and speaks an apology if n8n is unreachable. Every run, refusal,
and failure lands in data/audit.db.
