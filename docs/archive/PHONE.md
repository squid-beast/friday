# Phone access — Phase 7 (Tailscale + PWA)

Friday on your iPhone: the Mission Board and a text chat to the SAME brain —
same router, same confirm/PIN gates, same audit. Typing "stand down" on the
phone touches the control file at home and the daemon ends the session.

Nothing new listens on the network. The server stays on 127.0.0.1; Tailscale
proxies it into your private tailnet over TLS. Your tailnet already exists:
`lohiths-macbook-pro`, `iphone171`, and the Hostinger VPS are on it.

## Setup (once, ~2 minutes)

On the Mac:

```bash
tailscale serve --bg 8787
```

That publishes `https://lohiths-macbook-pro.<tailnet>.ts.net` → localhost:8787,
survives reboots, and is reachable ONLY by your tailnet devices.

On the iPhone:
1. Open the Tailscale app, make sure it's connected (it was last seen offline —
   toggle it on).
2. Safari → `https://lohiths-macbook-pro.<tailnet>.ts.net/chat`
   (`tailscale serve status` on the Mac prints the exact URL).
3. Share → **Add to Home Screen**. Friday is now an app icon.

`/chat` is the conversation; `/` is the Mission Board.

## Security posture

- The tailnet IS the auth boundary: WireGuard-encrypted, your devices only.
  Nothing is exposed to the public internet.
- The gates still hold over text: risk=confirm tools ask and require an
  explicit yes; risk=pin tools require the typed PIN digits; blocked refuses.
- Undo `tailscale serve` anytime: `tailscale serve --https=443 off`.

## Voice from the phone — Phase 7.6

Full spoken Friday on the iPhone: mic + barge-in over the tailnet. The page
and LiveKit signalling ride `tailscale serve` (HTTPS/WSS — iOS requires a
secure context for the mic); WebRTC media flows DIRECTLY over the tailnet's
WireGuard tunnel to the Mac. Nothing public, ever.

Setup (once):

1. `.env` — three lines (get the IP with `tailscale ip -4`):
   ```
   LIVEKIT_BIND_IP=100.118.41.0
   LIVEKIT_NODE_IP=100.118.41.0
   VOICE_WS_URL=wss://<mac>.<tailnet>.ts.net:8443
   ```
   (`tailscale serve status` prints the exact hostname.)
2. Second serve listener for LiveKit signalling:
   ```bash
   tailscale serve --bg --https=8443 http://127.0.0.1:7880
   ```
3. `make run` — docker LiveKit + the voice worker in dev mode.
4. Phone → the Friday PWA → **Voice** tab → **CONNECT** (the tap doubles as
   iOS's audio-playback permission gesture; allow the mic when asked).

Same brain, same persona, same barge-in as the room mic at home — and saying
"stand down" from the phone ends the session like anywhere else. Undo:
`tailscale serve --https=8443 off` and blank the three .env lines.
