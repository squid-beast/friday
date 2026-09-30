# Phase 6 — Public deploy: `friday.paypilotlabs.com` via Cloudflare Tunnel

> **Goal:** reach Friday from anywhere (no Tailscale needed), on your own subdomain, behind strong
> auth. **The Mac stays the brain** — the tunnel is a secure front door, not a re-host.
> **Do this phase LAST — only after Phase 5 voice-auth is armed.**

## Why the Mac stays the brain
Friday's mic, camera, screen recall, Calendar, Spotify, gestures, and the leos-brain vault are all
Mac-local. You expose the **app surface** (the dashboard on `127.0.0.1:8787`), not the filesystem.

## Build
1. **GitHub:** confirm `squid-beast/friday` is **private**; `.env` and `data/` gitignored (they
   are). Commit code + docs only. GitHub = version control / backup / deploy config — not runtime.
2. **Add `paypilotlabs.com` to Cloudflare** (nameservers, or delegate just the subdomain).
   *(It currently resolves elsewhere — moving/delegating DNS is the [LOHITH INPUT] step.)*
3. **cloudflared on the Mac:**
   - `brew install cloudflared`
   - `cloudflared tunnel login`
   - `cloudflared tunnel create friday`
   - config maps `friday.paypilotlabs.com → http://127.0.0.1:8787` (your dashboard port)
   - `cloudflared tunnel route dns friday friday.paypilotlabs.com`
4. **launchd:** add `com.jarvis.tunnel.plist` (mirror the other 8 agents) so the tunnel auto-starts
   and crash-restarts. Document install in `docs/DEPLOY.md`.
5. **Cloudflare Access (Zero Trust):** put an Access policy on `friday.paypilotlabs.com` = your email
   OTP / passkey. This is the "passkey/key" layer — a stranger is stopped at Cloudflare, before the
   app. Keep the `APP_ACCESS_KEY` cookie behind it as layer 2, and Phase 5 voice-auth as layer 3.

## Layered auth (the whole picture)
```
Internet → Cloudflare Access (identity)   [stranger stops here]
        → Cloudflare Tunnel → 127.0.0.1:8787 (your Mac)
        → APP_ACCESS_KEY cookie (device)
        → owner-voice verify (biometric, Phase 5)
        → PIN for destructive/calls
Always local: vault · screen · camera · gestures
Always offline: "Stand Down", camera off, menu-bar kill, hotkey
```

## [LOHITH INPUT]
Cloudflare account + `paypilotlabs.com` on Cloudflare; run the four cloudflared commands; set the
Access policy to your identity; confirm the GitHub repo is private.

## Acceptance
From your phone on **cellular, Tailscale OFF**: `friday.paypilotlabs.com` prompts Cloudflare Access →
app loads → a chat turn answers → "stand down" typed on the phone still cuts a home session. A
logged-out stranger never gets past Access. Keep Tailscale too as the internal path/fallback.
Then `/wrap` + snapshot.
