"""friday · integrations/server.py

The app shell: stdlib HTTP server bound to 127.0.0.1 ONLY, serving the built
SvelteKit UI (ui/build — prerendered pages + immutable assets) and the JSON
API. Reaching it from beyond this Mac rides tailscale serve/funnel behind the
APP_ACCESS_KEY gate; this process never listens on a real interface.

# ponytail: sync stdlib server, one household; swap for aiohttp if it ever matters
"""

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

from config.settings import get_settings
from integrations import api, api_conversation, api_devices, api_hud, api_studio, jobs_api
from integrations.access import AccessGate
from integrations.static_files import BUILD as _BUILD
from integrations.static_files import StaticFiles

# dashboard + the Jobs command center; every other non-API GET -> the SPA shell
PAGES = {"/": "index.html", "/jobs": "jobs.html"}
# The API surface is /api/v1/* only (unversioned aliases removed 2026-09-29).
GET_API = {
    "/api/v1/system/status": api.status,
    "/api/v1/metrics": api.summary,
    "/api/v1/agenda": api.today_view,
    "/api/v1/voice/session": api.voice_token,
}
POST_API = {
    "/api/v1/daemon/wake": api.daemon_wake,
    "/api/v1/daemon/stand-down": api.daemon_stand_down,
}
# route groups register themselves (one module per concern)
for _module in (api_hud, api_devices, api_studio, api_conversation, jobs_api):
    GET_API.update(_module.GET_API)
    POST_API.update(_module.POST_API)
ASK_PATHS = ("/api/v1/conversation",)
_bridge = None


def _get_bridge():
    """Production boots via boot_bridge() on the MAIN thread — native libs
    (chromadb/onnxruntime) segfault when first imported from a request-handler
    thread on macOS. The lazy path remains for tests with fakes."""
    global _bridge
    if _bridge is None:
        _bridge = boot_bridge()
    return _bridge


def boot_bridge():
    global _bridge
    if _bridge is None:
        import adapters.calendar  # noqa: F401 — objc framework: main-thread import
        from integrations.ask import BrainBridge

        _bridge = BrainBridge()
    return _bridge


class Handler(AccessGate, StaticFiles, BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if not self._gate():
            return
        path = unquote(urlsplit(self.path).path)
        if path in GET_API:
            return self._json(GET_API[path], {})
        if path.startswith("/api/v1/vision/snaps/"):
            return self._snap(path)
        if path == "/api/v1/gesture/frame":
            return self._gesture_frame()
        if path in PAGES:
            return self._file(_BUILD / PAGES[path])
        if path.startswith("/_app/") or path == "/manifest.webmanifest":
            return self._asset(path)
        if path.startswith("/api") or ".." in path or "\x00" in path or path.startswith("//"):
            return self.send_error(404)  # unknown API route / not a real client route
        return self._file(_BUILD / "index.html")  # SPA fallback: every route is the dashboard

    def do_POST(self) -> None:
        if not self._gate():
            return
        path = unquote(urlsplit(self.path).path)
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
        except (ValueError, json.JSONDecodeError):
            return self.send_error(400, "expected a JSON object body")
        if not isinstance(body, dict):
            return self.send_error(400, "expected a JSON object body")
        if path in ASK_PATHS:
            if "text" not in body:
                return self.send_error(400, 'expected {"text": "..."}')
            result = _get_bridge().ask(str(body["text"]))
            return self._send(json.dumps(result).encode(), "application/json")
        if path in POST_API:
            return self._json(POST_API[path], body)
        self.send_error(404)

    def _json(self, endpoint, body: dict) -> None:
        try:
            payload = endpoint(body)
        except ValueError as exc:
            return self.send_error(400, str(exc))
        except Exception:
            import logging

            logging.getLogger(__name__).warning("endpoint failed", exc_info=True)
            return self.send_error(502, "backend unavailable")
        self._send(json.dumps(payload).encode(), "application/json")

    def _send(self, body: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:  # localhost chatter stays out of logs
        return


def make_server(port: int = 0) -> ThreadingHTTPServer:
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main() -> int:
    port = get_settings().dashboard_port
    boot_bridge()  # main-thread boot: heavy native imports must never happen per-request
    server = make_server(port)
    print(f"Friday app -> http://127.0.0.1:{port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nApp down, sir.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
