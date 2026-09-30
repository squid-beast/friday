# Mission Board — the local dashboard (Phase D)

Visual tracking across platforms at **http://127.0.0.1:8787** — localhost only,
never reachable off the Mac. Data flows one way:

```
Instagram / BookYourSlot / leads / ...   (credentials live in n8n, on the VPS)
        └── n8n "metrics" workflows → JSON rows
                 └── Mac pulls hourly (integrations/n8n_pull.py, secret header)
                        └── data/metrics.db  ←also← integrations/jarvis_health.py
                               └── make dashboard → Mission Board
```

## Run it

```bash
make collect     # one sweep now (jarvis health + all configured webhooks)
make dashboard   # serve the board on http://127.0.0.1:8787
```

`make install-launchd` adds `com.jarvis.metrics` — a sweep at login and every
hour after. The board auto-refreshes every 60 seconds.

## Add a platform (no code)

1. In n8n, create a workflow: Webhook trigger (POST, same `X-Jarvis-Secret`
   header-auth credential as docs/N8N-SETUP.md) → pull the platform's numbers
   → **Respond to Webhook** with a JSON array:

   ```json
   [
     {"platform": "instagram", "metric": "reel_views_7d", "value": 12345},
     {"platform": "instagram", "metric": "follows_7d", "value": 84, "note": "reel spike"}
   ]
   ```

2. Register the path in `config/metrics.yaml` under `metric_webhooks`.
3. `make collect` — the card appears on the board.

Conventions: `platform` lowercase (one card each); `metric` snake_case with the
window in the name (`_7d`, `_24h`); `value` numeric. A dead webhook is skipped
and logged — it never kills the sweep.

## Suggested first four (matching the tools.yaml table)

| n8n workflow | returns |
|---|---|
| `/webhook/metrics-instagram` | reel_views_7d, reach_7d, follows_7d |
| `/webhook/metrics-bookyourslot` | bookings_7d, revenue_7d, mrr_usd |
| `/webhook/metrics-leads` | new_7d, contacted_7d, converted_7d |
| `/webhook/metrics-n8n-health` | runs_24h, failures_24h |

Jarvis's own card (wakes, tool runs/failures, camera looks) needs nothing —
it reads the local audit log.

## Asking Jarvis instead of looking

The same store is one adapter away from the voice side; "how did the reels do
this week, sir?" lands in a later Phase D chunk (see PLAN.md Phase D2).
