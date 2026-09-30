"""friday · tests/conftest.py

Tests must never read the developer's real .env — the suites were only green
before one existed (found 2026-08-11 when Stage 5 filled in VOICE_WS_URL and
"unconfigured" assertions started failing). Neutralize the env-file source
once for the whole run; fixtures that need a setting set OS env vars.
"""

from config.settings import Settings, get_settings

Settings.model_config["env_file"] = None
get_settings.cache_clear()
