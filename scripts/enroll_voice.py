"""friday · scripts/enroll_voice.py

Build sir's voiceprint for the per-turn owner-voice lock (Phase 5) from HIS OWN
16kHz recordings — the wake takes (scripts/record_wakeword.py), the normal-speech
clips (scripts/record_voice_verifier.py), and any extra reads in voice/enroll/.
Writes ONE L2-normalised mean embedding of the VOICED audio (VOICEPRINT_PATH,
gitignored) — the same trim the runtime lock scores — and prints held-out
(leave-one-out) scores to help choose VOICEPRINT_THRESHOLD.

Run: uv run python -m scripts.enroll_voice
"""

import sys
from pathlib import Path

import numpy as np

from adapters import voiceprint
from config.settings import get_settings

_REPO = Path(__file__).resolve().parents[1]
SOURCES = ("voice/wakeword/samples/wake", "voice/wakeword/samples/verifier-negative",
           "voice/enroll")


def clips(root: Path = _REPO) -> list[Path]:
    return sorted(p for d in SOURCES for p in (root / d).glob("*.wav"))


def main(argv: list[str] | None = None, *, root: Path = _REPO) -> int:
    s = get_settings()
    wavs = clips(root)
    if len(wavs) < 10:
        print(f"need at least 10 recordings of your voice; found {len(wavs)} in {SOURCES}")
        return 1
    embeddings = voiceprint.clip_embeddings(wavs, s.voiceprint_model_path)
    out = voiceprint.enroll(wavs, s.voiceprint_model_path, s.voiceprint_path)
    scores = voiceprint.leave_one_out(embeddings)  # held-out: how YOU will score at runtime
    low, p10 = float(np.min(scores)), float(np.percentile(scores, 10))
    print(f"voiceprint -> {out} ({len(embeddings)} usable clips of {len(wavs)})")
    print(f"your held-out clips vs the print: min {low:.2f}, 10th percentile {p10:.2f}, "
          f"median {float(np.median(scores)):.2f}")
    print(f"suggested VOICEPRINT_THRESHOLD ≈ {max(0.3, p10 - 0.05):.2f} — then have a friend "
          "speak: they must be refused")
    print("apply: set VOICE_LOCK_TURNS=true, restart the killswitch "
          "(launchctl kickstart -k gui/$(id -u)/com.friday.killswitch) and, if phone voice "
          "is on, `make phone-voice` again (the worker reads .env only at start)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
