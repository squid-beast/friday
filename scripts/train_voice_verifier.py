"""jarvis-life-os · scripts/train_voice_verifier.py

Train Friday's strict owner-voice verifier from Lohith's local recordings.
Positive clips come from the recorded wake phrase takes; negatives are normal
speech clips that do NOT contain the phrase.
"""

import argparse
import sys
from pathlib import Path

from openwakeword.custom_verifier_model import train_custom_verifier

_ROOT = Path(__file__).resolve().parent.parent
_SAMPLES = _ROOT / "voice" / "wakeword" / "samples"
_WAKE = _ROOT / "voice" / "wakeword" / "wake.onnx"
_OUT = _ROOT / "voice" / "wakeword" / "owner.joblib"


def _clips(path: Path) -> list[str]:
    return [str(p) for p in sorted(path.glob("*.wav"))]


def _need(path: Path, label: str) -> list[str]:
    clips = _clips(path)
    if not clips:
        raise ValueError(f"{label} missing: {path}")
    return clips


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--positive-dir", default=str(_SAMPLES / "wake"))
    parser.add_argument("--negative-dir", default=str(_SAMPLES / "verifier-negative"))
    parser.add_argument("--wake-model", default=str(_WAKE))
    parser.add_argument("--output", default=str(_OUT))
    args = parser.parse_args(argv)
    positive = _need(Path(args.positive_dir), "wake phrase clips")
    negative = _need(Path(args.negative_dir), "owner negative clips")
    model = Path(args.wake_model)
    if not model.is_file():
        raise ValueError(f"wake model missing: {model}")
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    train_custom_verifier(
        positive_reference_clips=positive,
        negative_reference_clips=negative,
        output_path=str(out),
        model_name=str(model),
    )
    print(f"Saved verifier -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
