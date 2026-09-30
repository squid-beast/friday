"""friday · integrations/static_files.py

File serving for the dashboard server as a request-handler mixin: built UI
assets, saved camera snaps, the live gesture frame. Every path is contained —
traversal resolves out and 404s; pathological paths 404 instead of crashing.
"""

from pathlib import Path

from config.settings import get_settings

BUILD = Path(__file__).resolve().parents[1] / "ui" / "build"
TYPES = {".html": "text/html; charset=utf-8", ".js": "application/javascript",
         ".css": "text/css", ".json": "application/json", ".png": "image/png",
         ".svg": "image/svg+xml", ".woff2": "font/woff2", ".jpg": "image/jpeg",
         ".jpeg": "image/jpeg", ".webmanifest": "application/manifest+json"}


class StaticFiles:
    """Mixin for BaseHTTPRequestHandler."""

    def _asset(self, path: str) -> None:
        """Built asset, contained to ui/build."""
        try:
            target = (BUILD / path.lstrip("/")).resolve()
            contained = target.is_relative_to(BUILD.resolve()) and target.is_file()
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
        ctype = TYPES.get(target.suffix, "application/octet-stream")
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if cache:
            self.send_header("Cache-Control", cache)
        self.end_headers()
        self.wfile.write(body)
