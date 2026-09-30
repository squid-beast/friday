"""friday · integrations/access.py

The app's access wall (APP_ACCESS_KEY) as a request-handler mixin. With the key
set, every request must carry it; a one-time ?key= paste is exchanged for an
HttpOnly cookie so the phone PWA authenticates once. The key is never logged.
"""

import hmac
from urllib.parse import parse_qs, urlsplit

from config.settings import get_settings


class AccessGate:
    """Mixin for BaseHTTPRequestHandler: call self._gate() first; False = handled."""

    def _gate(self) -> bool:
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
