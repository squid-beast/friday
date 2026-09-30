# Friday — Deployment Guide (GitHub + `friday.paypilotlabs.com`)

> **The Mac stays the brain.** Deploying Friday does not move her anywhere: the mic,
> speakers, calendar, Spotify, Obsidian vault, job files and every model call stay on
> this Mac. "Deploy" means two things only:
> 1. **GitHub** — version control and backup (`squid-beast/friday`, private).
> 2. **A secure front door** — `https://friday.paypilotlabs.com` reaches the dashboard
>    on `127.0.0.1:8787` through a **Cloudflare Tunnel**, behind **Cloudflare Access**.
>
> Supersedes `docs/DEPLOY-PLAN.md` (the older "re-host on the VPS" idea, kept for reference).

---

## 0 · The gate — do NOT open the front door until all are true

| # | Must be true | How to check |
|---|---|---|
| 1 | `make lint && make test` green | run them |
| 2 | `make doctor` says **all clear** | `make doctor` |
| 3 | `APP_ACCESS_KEY` is set (32 hex) | the dashboard answers **401** without the key: `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8787/` → `401` |
| 4 | **Owner-voice lock armed** (Phase 5) | dashboard header shows lock scope **every turn** (README §4 "Owner voice") |
| 5 | A spoken **PIN** is set | `.env` → `FRIDAY_PIN=` (4 digits) — note: no `risk: pin` tool is registered today, so this guards future PIN tools only |

**Be precise about what protects what.** The owner-voice lock and the spoken PIN guard
**spoken turns on the Mac's microphone only**. Every HTTP request — the dashboard, `/jobs`,
and text turns via `POST /api/v1/conversation` — is protected **solely by Cloudflare
Access + `APP_ACCESS_KEY`**. Anyone past both of those can type a command and answer a
confirm gate with "yes" (the same as your phone can). So: keep the Access policy to your
own identity, keep the key secret, and rotate it (`openssl rand -hex 16` →
`APP_ACCESS_KEY`, restart the dashboard) if a device is lost. #4 matters for the SPOKEN
side: once you rely on remote access, the house voice path shouldn't obey strangers either.

---

## 1 · GitHub — push the phase-wise history

The repo is **private** and currently **empty**; your local `main` already holds one commit
per phase (baseline → Phase 1 → 1b → 2 → 3 → 4 → 5 → 6 → docs). Secrets never enter git:
`.env*` (except `.env.example`), `data/`, **every voice artifact** — `voice/models/`
(speaker model + your voiceprint), `voice/wakeword/samples/` and `voice/enroll/` (your raw
recordings), `voice/wakeword/*.onnx|*.joblib` (models trained on your voice) —
`reference/`, `ui/build/`, `node_modules/`, `.coverage` and the compiled gesture binary
are all in `.gitignore` (pinned by tests/unit/test_gitignore.py).

```bash
cd ~/friday
git log --oneline            # review what will be published
git status                   # must be clean
git push -u origin main      # creates main on squid-beast/friday
```

If you created a branch or files on GitHub first (README/LICENSE from the web UI), fetch
and merge before pushing:

```bash
git fetch origin
git merge origin/<branch> --allow-unrelated-histories   # resolve, keep ours for code/README
git push -u origin main
```

Never force-push `main`. Pushing is always your action — Friday's tooling never pushes.

---

## 2 · Put `paypilotlabs.com` on Cloudflare  ⚠️ read before touching DNS

Today `paypilotlabs.com` uses the registrar's parking nameservers
(`apollo.dns-parking.com`, `athena.dns-parking.com`). Moving the domain to Cloudflare
**replaces the whole zone** — any existing records (the PayPilot Labs website, email MX,
verification TXT) must exist in Cloudflare BEFORE you switch nameservers, or they go dark.

1. Cloudflare dashboard → **Add a site** → `paypilotlabs.com` → Free plan.
2. Cloudflare scans existing records. **Compare them with your registrar's DNS page**;
   add anything missing (A/CNAME for the website, MX/TXT for email) — do not skip this.
3. At the registrar, change the nameservers to the two Cloudflare gives you.
4. Wait until Cloudflare shows the zone **Active** (minutes to hours).
5. Check: `dig +short NS paypilotlabs.com` → Cloudflare nameservers.

(Alternative that leaves the apex untouched: delegate only a subdomain — requires a
Cloudflare plan that supports subdomain zones. The full move above is the common path.)

---

## 3 · Create the tunnel (on the Mac)

```bash
brew install cloudflared
cloudflared tunnel login                 # browser: pick paypilotlabs.com
cloudflared tunnel create friday         # prints a TUNNEL-UUID + writes ~/.cloudflared/<UUID>.json
cp deploy/cloudflared-config.example.yml ~/.cloudflared/config.yml
#   edit ~/.cloudflared/config.yml: replace <you> and <TUNNEL-UUID>
cloudflared tunnel route dns friday friday.paypilotlabs.com
cloudflared tunnel --config ~/.cloudflared/config.yml run friday   # foreground smoke test, Ctrl-C
```

The config exposes **only** `http://127.0.0.1:8787` for `friday.paypilotlabs.com`;
everything else returns 404. The tunnel credentials JSON stays in `~/.cloudflared/`
(never in the repo).

---

## 4 · Cloudflare Access — the identity layer (stranger stops here)

Cloudflare dashboard → **Zero Trust** → **Access** → **Applications** → **Add** →
**Self-hosted**:

| Field | Value |
|---|---|
| Application domain | `friday.paypilotlabs.com` |
| Session duration | 24 hours (or shorter) |
| Policy name | `owner only` |
| Action | **Allow** |
| Include → Emails | your own email address only |
| Login method | One-time PIN (email) — and add a **passkey** if your plan offers it |

Test in a private window: `https://friday.paypilotlabs.com` must show the Cloudflare
login, not the dashboard.

---

## 5 · Run it permanently (launchd, like every other agent)

```bash
make tunnel        # installs + loads launchd/on-demand/tunnel/com.friday.tunnel.plist
make tunnel-off    # unloads + removes only the tunnel agent (core agents untouched)
```

The agent runs `cloudflared tunnel --config ~/.cloudflared/config.yml run friday`,
restarts on crash (KeepAlive) and logs to
`~/Library/Application Support/Friday/logs/tunnel.log`.

---

## 6 · The layered front door (the whole picture)

```
WEB / API (phone, browser, curl):
Internet ─▶ Cloudflare Access (identity: your email OTP / passkey)   ← a stranger stops here
         ─▶ Cloudflare Tunnel ─▶ 127.0.0.1:8787 on the Mac
         ─▶ APP_ACCESS_KEY cookie / Bearer (device)                   ← 401 without it
         ─▶ typed "yes" answers confirm gates (no voice/PIN check on this path)

VOICE (the Mac's microphone only):
mic ─▶ offline kill intents (any voice)
    ─▶ owner-voice lock, every spoken turn (biometric, Phase 5)     ← strangers refused
    ─▶ spoken "yes" for confirm tools · spoken PIN for PIN tools
Always local : vault · calendar · Spotify · job files · models' API keys
Always offline: "Stand down" · camera/screen off · menu-bar 😴 kill
```

---

## 7 · Acceptance (from your phone, on cellular, Tailscale OFF)

1. `https://friday.paypilotlabs.com` → Cloudflare Access login → your email code.
2. First visit: append `?key=<APP_ACCESS_KEY>` once → the dashboard loads (year cookie).
3. `/jobs` works; the recent-conversation card shows your last spoken turns.
4. A text turn via the API answers:
   `curl -s -H "Authorization: Bearer <key>" -H 'Content-Type: application/json' -d '{"text":"hello"}' https://friday.paypilotlabs.com/api/v1/conversation`
   (through Access you'll also need a Cloudflare **service token** for curl — or test from the browser).
5. `POST /api/v1/daemon/stand-down` (Bearer key) ends a home voice session.
6. A logged-out stranger never gets past step 1.

---

## 8 · Retire the public Tailscale Funnel (after §7 passes)

Today the dashboard is ALSO public through Tailscale Funnel
(`https://lohiths-macbook-pro.<tailnet>.ts.net`, key-gated). Once Cloudflare Access is
live, turn Funnel off and keep the private tailnet path as the fallback:

```bash
tailscale funnel status          # see what is public
tailscale funnel --https=443 off # stop PUBLIC exposure of port 443 (tailnet serve stays)
tailscale serve status           # the tailnet path should still be listed
```

If your CLI rejects `off`, `tailscale funnel reset` clears the funnel config; funnel and
serve share one config, so re-add the private path afterwards with
`tailscale serve --bg 8787` and confirm with `tailscale serve status`.

---

## 9 · Rollback

| Want | Do |
|---|---|
| Close the front door now | `make tunnel-off` (instant; the Mac is unreachable publicly) |
| Remove the tunnel | `cloudflared tunnel delete friday` + delete the `friday` DNS record in Cloudflare |
| Lock everyone out, keep tunnel | Cloudflare Access → policy → remove your email (or disable the app) |
| Roll the code back | `git log` → `git revert <commit>` (never rewrite pushed history) or copy from `~/friday-snapshots/` |

---

## 10 · Troubleshooting

| Symptom | Cause → fix |
|---|---|
| 502 / "tunnel error" | dashboard down → `launchctl kickstart -k gui/$(id -u)/com.friday.dashboard` |
| 1033 / tunnel not connected | agent down → `tail ~/Library/Application\ Support/Friday/logs/tunnel.log`, `make tunnel` |
| 401 after Access login | the Friday access key cookie is missing → open once with `?key=` |
| Access loop / no email code | policy email typo, or the domain isn't Active in Cloudflare yet |
| Website on the apex broke | a DNS record was not copied in §2 step 2 — add it in Cloudflare |
