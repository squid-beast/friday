"""friday · tests/unit/test_gitignore.py — PRIVACY (written before the fix)

Voice recordings, voice-trained models, the speaker model and the enrolled
voiceprint are biometric: they must never be committable, whatever the TODO
order (record -> enroll -> push). Secrets and runtime state likewise.
"""

import subprocess
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(not (_REPO / ".git").exists(), reason="not a git checkout")

PRIVATE = [
    ".env", ".env.local", "data/x.db",
    "voice/models/wespeaker_en_voxceleb_CAM++.onnx", "voice/models/owner_voiceprint.npy",
    "voice/enroll/read_01.wav",
    "voice/wakeword/samples/wake/near_quiet_01.wav",
    "voice/wakeword/samples/verifier-negative/negative_01.wav",
    "voice/wakeword/wake.onnx", "voice/wakeword/owner.joblib",
]
PUBLIC = [".env.example", "voice/wakeword/README.md", "voice/owner_lock.py"]


def _ignored(path: str) -> bool:
    return subprocess.run(["git", "check-ignore", "-q", path], cwd=_REPO,
                          check=False).returncode == 0


@pytest.mark.parametrize("path", PRIVATE)
def test_private_and_biometric_paths_are_never_committable(path: str) -> None:
    assert _ignored(path), f"{path} would be committed"


@pytest.mark.parametrize("path", PUBLIC)
def test_source_and_docs_stay_tracked(path: str) -> None:
    assert not _ignored(path)
