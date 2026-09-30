"""jarvis-life-os · integrations/server.py

The app shell: stdlib HTTP server bound to 127.0.0.1 ONLY, serving the built
SvelteKit UI (ui/build — prerendered pages + immutable assets) and the JSON
API. Reaching it from beyond this Mac rides tailscale serve/funnel behind the
APP_ACCESS_KEY gate; this process never listens on a real interface.

# ponytail: sync stdlib server, one household; swap for aiohttp if it ever matters
"""

import hmac
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from config.settings import get_settings
from integrations import api, jobs_api

_BUILD = Path(__file__).resolve().parents[1] / "ui" / "build"
# dashboard + the Jobs command center; every other non-API GET -> the SPA shell
PAGES = {"/": "index.html", "/jobs": "jobs.html"}
_TYPES = {".html": "text/html; charset=utf-8", ".js": "application/javascript",
          ".css": "text/css", ".json": "application/json", ".png": "image/png",
          ".svg": "image/svg+xml", ".woff2": "font/woff2", ".jpg": "image/jpeg",
          ".jpeg": "image/jpeg", ".webmanifest": "application/manifest+json"}

# The professional surface is /api/v1/* (docs/API.md). The unversioned paths
# are deprecated aliases kept so older installed phones never break.
GET_API = {
    "/api/v1/system/status": api.status,
    "/api/v1/metrics": api.summary,
    "/api/v1/agenda": api.today_view,
    "/api/v1/studio/queue": api.content_list,
    "/api/v1/voice/session": api.voice_token,
    "/api/v1/vision/snaps": api.vision_snaps,
    "/api/v1/gesture/state": api.gesture_state,
    "/api/v1/hud": api.hud,
    "/api/status": api.status, "/api/summary": api.summary,
    "/api/today": api.today_view, "/api/content": api.content_list,
    "/api/voice-token": api.voice_token,
}
POST_API = {
    "/api/v1/daemon/wake": api.daemon_wake,
    "/api/v1/daemon/stand-down": api.daemon_stand_down,
    "/api/v1/studio/queue/refresh": api.content_refresh,
    "/api/v1/studio/publish": api.content_publish,
    "/api/v1/studio/skip": api.content_skip,
    "/api/v1/automations/detail": api.automation_detail,
    "/api/v1/vault/open": api.vault_open,
    "/api/v1/gesture/control": api.gesture_control,
    "/api/content/refresh": api.content_refresh,
    "/api/content/publish": api.content_publish,
    "/api/content/skip": api.content_skip,
}
GET_API.update(jobs_api.GET_API)  # Jobs command center (integrations/jobs_api.py)
POST_API.update(jobs_api.POST_API)
ASK_PATHS = ("/api/v1/conversation", "/api/ask")
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


class Handler(BaseHTTPRequestHandler):
    def _gate(self) -> bool:
        """True = proceed. With APP_ACCESS_KEY set, every request must carry the
        key; a one-time ?key= paste is exchanged for an HttpOnly cookie so the
        phone PWA authenticates once. The key itself is never logged."""
        key = get_settings().app_access_key
        if not key:
            return True  # localhost/tailnet posture, unchanged
        parts = urlsplit(self.path)
        cookies = dict(
            pair.strip().split("=", 1)
            for pair in self.headers.get("Cookie", "").split(";")
            if "=" in pair
        )
        auth = self.headers.get("Authorization", "")
        supplied = (
            parse_qs(parts.query).get("key", [""])[0]
            or cookies.get("friday_key", "")
            or cookies.get("jarvis_key", "")
            or auth.removeprefix("Bearer ").strip()
        )
        if not hmac.compare_digest(supplied.encode(), key.encode()):
            self.send_error(401, "access key required")
            return False
        if "key" in parse_qs(parts.query):  # one-time paste -> cookie + clean URL
            self.send_response(303)
            self.send_header("Location", parts.path or "/")
            self.send_header(
                "Set-Cookie",
                f"friday_key={key}; Path=/; Max-Age=31536000; HttpOnly; SameSite=Lax",
            )
            self.send_header("Content-Length", "0")
            self.end_headers()
            return False
        return True

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

    def _asset(self, path: str) -> None:
        """Built asset, contained to ui/build — traversal resolves out, 404s;
        pathological paths (null bytes etc.) 404 instead of crashing."""
        try:
            target = (_BUILD / path.lstrip("/")).resolve()
            contained = target.is_relative_to(_BUILD.resolve()) and target.is_file()
        except (ValueError, OSError):
            return self.send_error(404)
        if not contained:
            return self.send_error(404)
        cache = "public, max-age=31536000, immutable" if "/immutable/" in path else None
        self._file(target, cache)

    def _snap(self, path: str) -> None:
        """A saved camera snap, contained to the snaps dir (traversal/null-byte 404)."""
        snaps = Path(get_settings().vision_snaps_dir)
        name = path[len("/api/v1/vision/snaps/"):]
        name = name if name.endswith(".jpg") else name + ".jpg"
        try:
            target = (snaps / name).resolve()
            contained = target.is_relative_to(snaps.resolve()) and target.is_file()
        except (ValueError, OSError):
            return self.send_error(404)
        if not contained:
            return self.send_error(404)
        self._file(target)

    def _gesture_frame(self) -> None:
        """The live camera frame for /gesture — no-cache so each <img> refresh gets
        the newest. 404 until the gesture agent is running and writing frames."""
        frame = Path(get_settings().gesture_frame_file)
        if not frame.is_file():
            return self.send_error(404)
        self._file(frame, cache="no-store")

    def _file(self, target: Path, cache: str | None = None) -> None:
        if not target.is_file():
            return self.send_error(404, "UI not built (cd ui && npm run build)")
        ctype = _TYPES.get(target.suffix, "application/octet-stream")
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if cache:
            self.send_header("Cache-Control", cache)
        self.end_headers()
        self.wfile.write(body)

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
