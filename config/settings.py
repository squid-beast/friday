"""friday · config/settings.py

Single config entry point (pydantic-settings, reads .env). Nothing else reads os.environ.
Keys default to "" — adapter factories raise on missing keys, not Settings, because
later-phase keys (n8n, screenpipe, ...) are legitimately blank until their phase.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Product identity
    assistant_name: str = "Friday"
    wake_phrase_text: str = "Hey Friday"
    stand_down_phrase_text: str = "Stand Down"

    # LLM — PLAN §6's `claude-*-latest` aliases don't exist; these are real model IDs.
    anthropic_api_key: str = ""
    model_smart: str = "claude-sonnet-5"
    model_fast: str = "claude-haiku-4-5"

    # Voice
    deepgram_api_key: str = ""
    cartesia_api_key: str = ""
    tts_voice_id: str = ""
    elevenlabs_api_key: str = ""  # optional fallback, unused in Phase 1

    # LiveKit (local)
    livekit_url: str = "ws://127.0.0.1:7880"
    livekit_api_key: str = "devkey"
    livekit_api_secret: str = ""

    # Runtime state lives OUTSIDE the repo so the checkout stays source-only.
    state_dir: str = Field(
        default=str(Path.home() / "Library" / "Application Support" / "Friday"),
        validation_alias="FRIDAY_STATE_DIR",
    )

    # Runtime memory (Phase 2) — chroma is embedded (PersistentClient), no server
    vault_path: str = "/Users/lohithkumar/leos-brain"
    vault_exclude: str = ""

    # Jobs command center: the nightly job engine's output folder (read + decisions)
    jobs_dir: str = "/Users/lohithkumar/Downloads/Jobs"
    jobs_tracker_note: str = "areas/career/target-companies.md"  # inside vault_path
    chroma_path: str = "db/chroma"
    checkpoint_db_path: str = "db/checkpoint.db"
    audit_db_path: str = "db/audit.db"

    # n8n (Phase 4)
    n8n_base_url: str = ""
    n8n_webhook_secret: str = ""
    n8n_api_key: str = ""  # public REST API (executions read for the HUD)

    # Vision (Phase 5)
    screenpipe_url: str = "http://127.0.0.1:3030"
    screenpipe_exclude: str = ""  # comma-separated app names never surfaced in recall
    moondream_endpoint: str = "http://127.0.0.1:2020/v1"  # local Moondream Station
    vision_snaps_dir: str = "images/vision/snaps"  # each camera look saved here for the UI
    vision_snaps_keep: int = 20  # keep the most recent N snaps; prune older
    camera_off_file: str = "control/camera_off"  # flag: camera refuses while present
    gesture_state_file: str = "gesture/state.json"  # G1: latest hand landmarks for /gesture
    gesture_frame_file: str = "gesture/frame.jpg"   # G2: live camera frame for the feed
    gesture_control_file: str = "gesture/control_on"  # G2: cursor control armed while present
    screen_off_file: str = "control/screen_off"  # flag: recall refuses while present
    browser_profile_dir: str = "~/friday-chrome"  # dedicated Chrome profile, never sir's own
    browser_max_steps: int = 15
    chrome_path: str = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

    # Sessions (Phase 3)
    session_silence_timeout_s: int = 120
    wake_threshold: float = 0.6
    wake_model_path: str = ""  # blank = bundled "hey jarvis" until a custom Friday wake exists
    wake_verifier_path: str = ""  # strict owner-voice lock (.joblib), optional until armed
    wake_verifier_threshold: float = 0.18  # owner-voice acceptance threshold for wake frames
    wake_require_verifier: bool = False  # strict mode: fail closed until the verifier exists
    kill_model_path: str = ""  # blank = spoken OFFLINE kill unarmed (hotkey/menu-bar still cut)
    # blank = global kill-hotkey OFF. pynput's system-wide keyboard hook costs
    # ~⅛ of a CPU core while you type all day; menu-bar 😴 + spoken "stand down"
    # remain as kill paths. Set e.g. "cmd+alt+j" (⌥⌘J) to re-enable.
    hotkey: str = ""
    stand_down_file: str = "control/stand_down"  # agent touches it; daemon acts on it

    # Wake routine — on the FIRST wake of the day, open sir's apps + tabs (a
    # morning launch). Also fired anytime by the "open my apps" tool. Mac-only
    # (subprocess `open`), fully offline. Blank list / disabled = no-op.
    wake_apps_enabled: bool = True
    wake_launch_spotify: bool = True
    wake_urls: str = (
        "https://www.instagram.com,https://github.com,"
        "https://mail.google.com,http://127.0.0.1:8787"
    )  # comma-separated; last one is the Friday cockpit UI

    # Highest-risk gate (Phase 6) — spoken 4-digit PIN; blank locks risk=pin tools shut
    friday_pin: str = ""

    # Calling (PIN-gated) — Friday places a real phone call in sir's stead via a
    # telephony provider. Blank provider = the tool refuses (unconfigured). See
    # docs/CALLS.md for what to sign up for. Provider: "vapi" | "twilio" | "".
    telephony_provider: str = ""
    telephony_api_key: str = ""
    telephony_from_number: str = ""  # the number calls originate from (E.164)
    telephony_agent_id: str = ""  # provider-side assistant/agent id (Vapi), optional

    # Weather sense (Open-Meteo, keyless) — the city Friday reports on
    weather_city: str = ""

    # Dashboard (Phase D) — localhost only, never bound to a real interface
    dashboard_port: int = 8787
    logs_dir: str = "logs"
    # Access gate for the app when a proxy (tailscale serve/funnel) exposes it
    # beyond this Mac. Blank = open (localhost/tailnet); set = every request
    # must carry the key (?key= once -> cookie, or Authorization: Bearer).
    app_access_key: str = ""

    # Content Studio (Phase 7.5) — both webhooks live on n8n, which holds the IG creds
    content_trending_webhook: str = ""  # returns trending items JSON; blank = unarmed
    content_publish_webhook: str = ""  # posts an item to Instagram; blank = unarmed
    content_db_path: str = "db/content.db"
    metrics_db_path: str = "db/metrics.db"
    reminders_path: str = "db/reminders.json"
    mood_path: str = "db/mood.json"

    # Phone voice (Phase 7.6) — wss URL the phone dials (tailscale serve -> livekit);
    # blank = the Voice screen shows setup instead of a connect button
    voice_ws_url: str = ""

    # Observability (optional)
    langsmith_api_key: str = ""
    langsmith_project: str = "friday"

    def model_post_init(self, __context) -> None:
        state_dir = Path(self.state_dir).expanduser()
        self.state_dir = str(state_dir)
        for field in (
            "chroma_path",
            "checkpoint_db_path",
            "audit_db_path",
            "vision_snaps_dir",
            "camera_off_file",
            "gesture_state_file",
            "gesture_frame_file",
            "gesture_control_file",
            "screen_off_file",
            "stand_down_file",
            "logs_dir",
            "content_db_path",
            "metrics_db_path",
            "reminders_path",
            "mood_path",
        ):
            value = Path(getattr(self, field)).expanduser()
            if not value.is_absolute():
                value = state_dir / value
            setattr(self, field, str(value))


@lru_cache
def get_settings() -> Settings:
    return Settings()
