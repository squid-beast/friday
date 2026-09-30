# Friday — Deploy Plan: GitHub → VPS → friday.paypilotlabs.com

> Companion to `docs/PLAN-NEXT.md` (features) and `docs/SYSTEM-REVIEW.md` (current state).
> Goal: Friday's dashboard + Jobs command center live at **https://friday.paypilotlabs.com**, running on the
> Hostinger VPS (KVM 4, 2.25.89.115), deployed automatically from a **private** GitHub repo, secure by default,
> while the Mac keeps doing what only the Mac can do (voice, Spotify, Chrome submissions, local files).
> Run ONE phase per Claude Code session. Paste the prompt at the end of each phase.

---

## 0. Target architecture

```
Phone / any browser
      │ HTTPS (TLS by Caddy, Let's Encrypt)
      ▼
friday.paypilotlabs.com ──► VPS (Docker Compose)
                              ├─ caddy        :80/:443 only public ports
                              ├─ friday-cloud  gateway: UI + auth (email+password+TOTP) + jobs API + /health
                              │                SQLite in a volume (single user)
                              └─ ollama        (later) bound to the tailnet only — NEVER public
                                    ▲
                                    │ Tailscale (private network) + device token
                                    ▼
Mac (friday-mac agent, FRIDAY_MODE=mac)
   voice · Spotify · open apps · Chrome job submissions · ~/Downloads/Jobs · Obsidian vault
   pushes job batches/progress UP, pulls Approve/Skip/answers DOWN (every 30 s)
Nightly Claude job run ──► ~/Downloads/Jobs on the Mac ──► synced to the cloud dashboard
```

What stays **off** the cloud: the Obsidian vault contents, `me.json`, resumes/letters PDFs (the cloud shows the
list; "Open resume" works when the Mac is online), `.env` secrets of the Mac, any audio/screen data.

---

## 1. What Lohith does by hand (≈45 minutes, once)

- [ ] **GitHub:** confirm `github.com/squid-beast/friday` exists and is **Private** (Settings → General → Danger
      zone → visibility). If it doesn't exist, create it private and empty.
- [ ] **DNS:** in the panel that manages `paypilotlabs.com` (Hostinger hPanel → Domains → DNS / Nameservers, or
      Cloudflare if you moved it): add record **A · name `friday` · value `2.25.89.115` · TTL 300**.
- [ ] **VPS SSH key:** hPanel → VPS → Settings → SSH keys → add your Mac's public key (`~/.ssh/id_ed25519.pub`;
      create with `ssh-keygen -t ed25519` if missing). Confirm `ssh root@2.25.89.115` works.
- [ ] **Tailscale:** install on the VPS (`curl -fsSL https://tailscale.com/install.sh | sh && tailscale up`) and
      approve it in the Tailscale admin console (your Mac is already on the tailnet).
- [ ] **Tell Claude** which containers already run on the VPS (hPanel shows Docker; n8n/OpenClaw?) so nothing
      existing is broken.
- [ ] Keep your **authenticator app** (Google Authenticator / 1Password / Authy) ready for the first login.

---

## Phase D1 — Repo hygiene & GitHub (safe first push)
1. **Lift the no-git rule on purpose:** update `CLAUDE.md` + `memory-bank/DECISIONS.md` ("2026-09-28: Lohith
   decided to use the private GitHub repo; secrets and personal data never committed"). Keep `make snapshot`.
2. Extend `.gitignore`: `db/`, `*.db`, `*.sqlite*`, `images/`, `reference/` (15 MB upstream source), `.coverage`,
   `logs/`, `*.log`, `control/`, `gesture/state.json`, `gesture/frame.jpg`.
3. **Secret scan before any push:** run `gitleaks detect --source . --log-opts="--all"` (history too) and
   `gitleaks detect --no-git`. Any hit in history → rewrite with `git filter-repo` and **rotate that key**
   (Anthropic, Deepgram, Cartesia, n8n, APP_ACCESS_KEY). Nothing is pushed until the scan is clean.
4. Commit in logical chunks, push `main`. Protect `main` (require CI green; no force-push).
5. GitHub Actions `ci.yml`: `uv sync` → `ruff check` → `pytest tests/unit` → `npm ci && npm run build` in `ui/`.
   Add `gitleaks` as a CI step so a secret can never be merged.
**Accept:** repo private, CI green, gitleaks clean on history.
**Prompt:** `Do Phase D1 of docs/DEPLOY-PLAN.md. Show me the gitleaks result before the first push and wait for my OK.`

## Phase D2 — Split into cloud mode and Mac mode
1. `FRIDAY_MODE=cloud|mac` in `config/settings.py`. Cloud: no voice, Spotify, open-apps, camera, launchd,
   vault or `~/Downloads` access — those adapters report "Mac only". Mac: today's behaviour.
2. `Dockerfile` (multi-stage): Node stage builds `ui/`; Python 3.12-slim + uv stage runs
   `python -m integrations.server` as a non-root user; `HEALTHCHECK` on `/api/v1/health`.
3. `deploy/docker-compose.yml`: `caddy` + `friday-cloud` (+ `ollama` commented out). Volumes: `friday-data`
   (SQLite), `caddy-data` (certs). Docker log rotation (`max-size: 10m`, `max-file: 3`).
4. Every jobs/API read in cloud mode comes from SQLite (fed by sync, Phase D4), not the filesystem.
**Accept:** `docker compose up` locally serves the UI; tests for both modes green.
**Prompt:** `Do Phase D2 of docs/DEPLOY-PLAN.md.`

## Phase D3 — Login before anything is public (= PLAN-NEXT Phase 6)
Email + password (Argon2id) + authenticator TOTP with QR enrolment + 10 backup codes; lockout after 5 failures
with back-off; session cookie `Secure; HttpOnly; SameSite=Strict`; CSRF token on every POST; login audit;
first-run enrolment only from the Mac/tailnet (a one-time setup token printed in the container log).
The old `APP_ACCESS_KEY` gate stays only for the Mac agent's device token.
**Accept:** TDD suite for login, lockout, backup codes, CSRF; no page or API readable without a session.
**Prompt:** `Do Phase D3 of docs/DEPLOY-PLAN.md (TDD, security first).`

## Phase D4 — Mac ↔ cloud sync (the live link)
1. Cloud API (device-token auth, tailnet or HTTPS): `POST /api/v1/sync/jobs` (batch.json, progress, tracker
   counts), `GET /api/v1/sync/decisions?since=` (Approve/Skip/answers made in the cloud UI).
2. Mac agent loop (runs inside the Mac dashboard process, every 30 s, backs off when offline): push changed batch
   files (by mtime hash), pull decisions and write `~/Downloads/Jobs/_engine/state/decisions_<batch>.json`
   atomically (same format the nightly run reads). Conflict rule: newest timestamp wins, both sides audited.
3. "Open resume/letter/folder" from the cloud UI → queued command the Mac agent executes when online.
**Accept:** approve on the phone → decisions file on the Mac updated within 30 s; tests with a fake server.
**Prompt:** `Do Phase D4 of docs/DEPLOY-PLAN.md.`

## Phase D5 — Harden the VPS (before DNS points at it)
Create user `deploy` (docker group, no sudo password login); SSH keys only (`PasswordAuthentication no`,
`PermitRootLogin prohibit-password`); `ufw` allow 22 (or only from the tailnet), 80, 443, deny the rest;
`fail2ban` for sshd; `unattended-upgrades`; Docker + compose plugin; inventory and keep existing containers;
confirm nothing listens publicly except 22/80/443 (`ss -tlnp`).
**Accept:** a port scan from outside shows only 22/80/443.
**Prompt:** `Do Phase D5 of docs/DEPLOY-PLAN.md on the VPS over SSH. List every change before making it.`

## Phase D6 — Subdomain + HTTPS
`deploy/Caddyfile`: `friday.paypilotlabs.com { reverse_proxy friday-cloud:8787 }` + security headers (HSTS,
CSP self-only, X-Frame-Options DENY, Referrer-Policy) + request-size limit + login rate limit.
Caddy gets the Let's Encrypt certificate automatically once the A record resolves.
**Accept:** `https://friday.paypilotlabs.com` shows the login page with a valid certificate; SSL Labs grade A.
**Prompt:** `Do Phase D6 of docs/DEPLOY-PLAN.md.`

## Phase D7 — Automatic deploys from GitHub
`deploy.yml`: on push to `main` after CI passes → build image → push to **GHCR (private)** tagged with the commit
SHA → SSH (deploy key, `deploy` user) → `docker compose pull && docker compose up -d` → smoke test `/api/v1/health`
→ on failure, re-deploy the previous SHA automatically. Secrets live in GitHub Environments + a root-only
`/opt/friday/.env` on the VPS — never in the repo.
**Accept:** a README change on `main` is live in < 5 minutes; a broken build never replaces a working one.
**Prompt:** `Do Phase D7 of docs/DEPLOY-PLAN.md.`

## Phase D8 — Backups, monitoring, alerts
Nightly `sqlite3 .backup` → encrypted copy kept 14 days on the VPS + pulled to the Mac over Tailscale;
uptime check on `/api/v1/health` (free healthchecks.io or UptimeRobot) → push/email alert; `/health` includes
last sync time from the Mac and the last nightly job run; weekly restore test.
**Accept:** stop the container → alert within 5 minutes; restore from last night's backup works.
**Prompt:** `Do Phase D8 of docs/DEPLOY-PLAN.md.`

## Phase D9 — (later) Models on the VPS
Ollama container on the internal network, reachable only from Friday and the tailnet; small models (Qwen3 4B /
1.7B, nomic-embed-text) for background work; the Mac stays the fast path for live voice (PLAN-NEXT Phase 5).

---

## Go-live checklist
- [ ] gitleaks clean (tree + history), repo private, CI green
- [ ] Login + TOTP + backup codes work; lockout tested; no unauthenticated route returns data
- [ ] Only 22/80/443 open; SSH keys only; fail2ban on
- [ ] Valid TLS on friday.paypilotlabs.com; security headers present
- [ ] Mac sync round-trip < 30 s; Approve on phone reaches the Mac's decisions file
- [ ] Backups + uptime alert + rollback tested once

## Order with the feature plan
`PLAN-NEXT` Phase 1 (stabilize) → D1 → D2 → D3 → D4 → D5 → D6 → D7 → D8 → then PLAN-NEXT Phases 2–5, 7, 9.
Nothing goes public (D6) before D3 (login) is done.
