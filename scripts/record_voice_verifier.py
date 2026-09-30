"""friday · scripts/record_voice_verifier.py

Record negative clips for Friday's owner-voice verifier. These clips must NOT
contain the wake phrase; they should be normal speech from Lohith so the
verifier learns what his voice sounds like outside the trigger phrase too.
"""

import sys
import wave
from pathlib import Path

import sounddevice as sd

SAMPLE_RATE = 16_000
SECONDS = 3
COUNT = 25
PROMPTS = (
    "say what you are working on today",
    "describe where you are",
    "talk about your plans for tomorrow",
    "name three songs you like",
    "describe what is on your desk",
)
_OUT_DIR = (
    Path(__file__).resolve().parent.parent
    / "voice" / "wakeword" / "samples" / "verifier-negative"
)


def record_one(path: Path, seconds: int = SECONDS) -> None:
    frames = sd.rec(int(seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="int16")
    sd.wait()
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SAMPLE_RATE)
        f.writeframes(frames.tobytes())


def main() -> int:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Recording {COUNT} owner-voice clips -> {_OUT_DIR}")
    print('Do NOT say "Hey Friday". Speak naturally for ~3 seconds after Enter.\n')
    for i in range(1, COUNT + 1):
        path = _OUT_DIR / f"negative_{i:02d}.wav"
        if path.exists():
            continue
        prompt = PROMPTS[(i - 1) % len(PROMPTS)]
        input(f"[{i}/{COUNT}] {prompt} — Enter to record... ")
        record_one(path)
        print(f"    saved {path.name}")
    print("\nNegative set complete. Next: uv run python -m scripts.train_voice_verifier")
    return 0


if __name__ == "__main__":
    sys.exit(main())
