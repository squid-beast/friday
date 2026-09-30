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
    # llm_provider: anthropic (default) | openai | openrouter | gemini | compatible
    # (compatible = any OpenAI-compatible server at llm_base_url, e.g. Ollama/vLLM).
    # model_smart/fast are provider-specific ids; Claude ids on openai/openrouter/gemini
    # fall back to that provider's defaults; `compatible` requires explicit ids.
    llm_provider: str = "anthropic"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""
    openrouter_api_key: str = ""
    llm_base_url: str = ""  # LLM_PROVIDER=compatible only: your server's /v1 URL
    llm_api_key: str = ""  # LLM_PROVIDER=compatible only (optional; never the OpenAI key)
    model_smart: str = "claude-sonnet-5"
    model_fast: str = "claude-haiku-4-5"

    # Voice
    deepgram_api_key: str = ""
    cartesia_api_key: str = ""
    tts_voice_id: str = ""
    elevenlabs_api_key: str = ""  # optional fallback, unused in Phase 1
    # Voice out: tts_provider = cartesia (default) | openai | fishaudio
    tts_provider: str = "cartesia"
    openai_tts_model: str = "gpt-4o-mini-tts"  # takes per-turn tone instructions
    openai_tts_voice: str = "coral"
    fish_api_key: str = ""
    fish_voice_id: str = ""  # the cloned target voice (Fish Audio model/reference id)
    fish_model: str = "s1"  # S1 renders inline emotion tags like "(worried)"
    fish_emotion_enabled: bool = True

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
    # wake-score at which openWakeWord CONSULTS the verifier (not the acceptance bar — the
    # verifier's probability must still clear wake_threshold). Text-dependent: it learns
    # "sir saying the phrase" vs "sir saying anything else", never other speakers.
    wake_verifier_threshold: float = 0.18
    wake_require_verifier: bool = False  # strict mode: fail closed until the verifier exists
    # Per-turn owner-voice lock (Phase 5): every spoken turn scored vs sir's voiceprint.
    # Armed only when true; with the model or voiceprint missing it FAILS CLOSED.
    voice_lock_turns: bool = False
    voiceprint_model_path: str = "voice/models/wespeaker_en_voxceleb_CAM++.onnx"
    voiceprint_path: str = "voice/models/owner_voiceprint.npy"  # scripts/enroll_voice.py
    voiceprint_threshold: float = 0.5  # cosine; tune after enrollment (README TODO)
    kill_model_path: str = ""  # blank = spoken OFFLINE kill unarmed (hotkey/menu-bar still cut)
    # blank = global kill-hotkey OFF. pynput's system-wide keyboard hook costs
    # ~⅛ of a CPU core while you type all day; menu-bar 😴 + spoken "stand down"
    # remain as kill paths. Set e.g. "cmd+alt+j" (⌥⌘J) to re-enable.
    hotkey: str = ""
    stand_down_file: str = "control/stand_down"  # agent touches it; daemon acts on it
    pending_question_file: str = "control/pending_question.json"  # last check-in asked

    # Wake routine — on the FIRST wake of the day, open sir's apps + tabs (a
    # morning launch). Also fired anytime by the "open my apps" tool. Mac-only
    # (subprocess `open`), fully offline. Blank list / disabled = no-op.
    # Proactive check-ins: launchd com.friday.checkin nudges at 09:00/13:00/19:00
    proactive_checkins: bool = True
    wake_apps_enabled: bool = True
    wake_launch_spotify: bool = True
    wake_urls: str = (
        "https://www.instagram.com,https://github.com,"
        "https://mail.google.com,http://127.0.0.1:8787"
    )  # comma-separated; last one is the Friday cockpit UI

    # Highest-risk gate (Phase 6) — spoken 4-digit PIN; blank locks risk=pin tools shut
    friday_pin: str = ""

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
            "pending_question_file",
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
