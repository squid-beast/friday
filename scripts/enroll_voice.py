"""friday · scripts/enroll_voice.py

Build sir's voiceprint for the per-turn owner-voice lock (Phase 5) from HIS OWN
16kHz recordings — the wake takes (scripts/record_wakeword.py), the normal-speech
clips (scripts/record_voice_verifier.py), and any extra reads in voice/enroll/.
Writes ONE L2-normalised mean embedding (VOICEPRINT_PATH, gitignored) and
prints how each clip scores against it, to help choose VOICEPRINT_THRESHOLD.
Then set VOICE_LOCK_TURNS=true and restart the killswitch.

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
    out = voiceprint.enroll(wavs, s.voiceprint_model_path, s.voiceprint_path)
    scores = [voiceprint.score(voiceprint.load_wav(p), s.voiceprint_path,
                               s.voiceprint_model_path) for p in wavs]
    low, median = float(np.min(scores)), float(np.median(scores))
    print(f"voiceprint -> {out} ({len(wavs)} clips)")
    print(f"your clips vs the print: min {low:.2f}, median {median:.2f}")
    print(f"suggested VOICEPRINT_THRESHOLD ≈ {max(0.3, low - 0.05):.2f} "
          "(then test with a friend's voice: it must score BELOW it)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
