"""friday · scripts/record_wakeword.py

Guided recorder: 50 samples of a phrase for openWakeWord training, across
near/far/quiet/loud scenarios. Re-running resumes — existing takes are kept.

Usage:  uv run python -m scripts.record_wakeword                  # wake phrase
        uv run python -m scripts.record_wakeword --phrase standdown
Output: voice/wakeword/samples/<phrase>/<scenario>_<nn>.wav (16 kHz mono s16)
Then train per voice/wakeword/README.md.
"""

import argparse
import sys
import wave
from pathlib import Path

import sounddevice as sd

SAMPLE_RATE = 16_000
SECONDS = 3
SCENARIOS = [("near", 15), ("far", 15), ("quiet", 10), ("loud", 10)]  # 50 total
PHRASES = {"wake": "Hey Friday", "standdown": "Stand Down"}
TIPS = {
    "near": "arm's length from the Mac, normal voice",
    "far": "from across the room",
    "quiet": "soft late-night voice",
    "loud": "raised voice, as if the music is on",
}
_OUT_ROOT = Path(__file__).resolve().parent.parent / "voice" / "wakeword" / "samples"


def plan() -> list[tuple[str, int]]:
    return [(scenario, i) for scenario, count in SCENARIOS for i in range(1, count + 1)]


def record_one(path: Path, seconds: int = SECONDS) -> None:
    frames = sd.rec(int(seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="int16")
    sd.wait()
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SAMPLE_RATE)
        f.writeframes(frames.tobytes())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phrase", choices=sorted(PHRASES), default="wake")
    args = parser.parse_args(argv)
    phrase = PHRASES[args.phrase]
    out_dir = _OUT_ROOT / args.phrase
    out_dir.mkdir(parents=True, exist_ok=True)
    takes = plan()
    print(f'Recording {len(takes)} takes of "{phrase}" -> {out_dir}')
    print("Each take records for 3 seconds after you press Enter. Ctrl+C to pause anytime.\n")
    for n, (scenario, i) in enumerate(takes, start=1):
        path = out_dir / f"{scenario}_{i:02d}.wav"
        if path.exists():
            continue  # resume: keep earlier takes
        input(f'[{n}/{len(takes)}] {TIPS[scenario]} — Enter, then say "{phrase}"... ')
        record_one(path)
        print(f"    saved {path.name}")
    print("\nAll takes recorded. Next: voice/wakeword/README.md (training steps).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
