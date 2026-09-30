"""friday · gesture/spike.py

G0 runner: pipe the native hand-pose feed (gesture/handpose) through the pure
classifier and print the live gesture. This is the spike that proves the whole
chain works — camera -> Apple Vision -> 2D landmarks -> gesture — with NO Mac
control yet.

    make gesture                 # build the native binary (swiftc)
    uv run python -m gesture.spike   # run it; show your hand; Ctrl-C to stop

Run it from a terminal so macOS can prompt for Camera access the first time.
"""

import json
import subprocess
import sys
from pathlib import Path

from gesture.classifier import classify

_BINARY = Path(__file__).resolve().parent / "handpose"


def gesture_for_line(line: str) -> str | None:
    """One native JSON frame ({"hands":[...]}) -> the first hand's gesture, or None."""
    try:
        payload = json.loads(line)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    hands = payload.get("hands") if isinstance(payload, dict) else None
    if not hands:
        return None
    landmarks = {k: tuple(v) for k, v in (hands[0].get("landmarks") or {}).items()}
    gesture = classify(landmarks)
    return gesture if gesture != "none" else None


def main() -> int:
    if not _BINARY.exists():
        print("Build the native spike first:  make gesture", file=sys.stderr)
        return 1
    proc = subprocess.Popen([str(_BINARY)], stdout=subprocess.PIPE, text=True, bufsize=1)
    last = None
    try:
        for line in proc.stdout or []:
            gesture = gesture_for_line(line.strip())
            if gesture and gesture != last:
                print(f"👋 {gesture}")
                last = gesture
    except KeyboardInterrupt:
        pass
    finally:
        proc.terminate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
