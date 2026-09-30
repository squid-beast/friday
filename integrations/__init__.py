"""jarvis-life-os · integrations/

Platform metric collectors + the local dashboard. Same discipline as adapters/:
one platform per file, network code allowed HERE only, credentials stay in n8n
(the Mac pulls metrics from authed n8n webhooks — no platform tokens on disk).
The dashboard binds to 127.0.0.1 only; nothing here is reachable off-machine.
"""
