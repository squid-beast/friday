"""friday · adapters/voiceprint.py

Text-independent speaker embeddings for the owner-voice lock. Model: WeSpeaker
CAM++ (VoxCeleb, Apache-2.0) as ONNX — `voice/models/wespeaker_en_voxceleb_CAM++.onnx`
(29.3MB, sha256 c46fad10…ec54ef, from k2-fsa/sherpa-onnx releases). Features:
80-bin Kaldi fbank (kaldi-native-fbank, dither 0) + per-utterance mean
normalisation; samples at int16 scale (model metadata normalize_samples=0).
numpy + onnxruntime only — no torch. The enrolled voiceprint is ONE L2-normalised
mean embedding saved as .npy (biometric: lives in gitignored voice/models/).
"""

import wave
from functools import lru_cache
from math import gcd
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[1]
SR = 16_000


def _abs(path: str) -> Path:
    p = Path(path).expanduser()
    return p if p.is_absolute() else _REPO / p


@lru_cache(maxsize=2)
def _session(model_path: str):
    import onnxruntime as ort

    return ort.InferenceSession(str(_abs(model_path)), providers=["CPUExecutionProvider"])


def features(pcm16k: np.ndarray) -> np.ndarray:
    import kaldi_native_fbank as knf

    opts = knf.FbankOptions()
    opts.frame_opts.dither = 0
    opts.frame_opts.samp_freq = SR
    opts.mel_opts.num_bins = 80
    fbank = knf.OnlineFbank(opts)
    fbank.accept_waveform(SR, (pcm16k * 32768.0).astype(np.float32).tolist())
    fbank.input_finished()
    feats = np.stack([fbank.get_frame(i) for i in range(fbank.num_frames_ready)])
    return (feats - feats.mean(axis=0)).astype(np.float32)


def embed(pcm16k: np.ndarray, model_path: str) -> np.ndarray:
    feats = features(pcm16k)[None, ...]
    out = _session(model_path).run(None, {"feats": feats})[0][0]
    return out / (np.linalg.norm(out) + 1e-9)


def load_wav(path: str | Path) -> np.ndarray:
    """16-bit PCM WAV -> 16kHz mono float32 (the recorders write exactly this)."""
    with wave.open(str(path), "rb") as w:
        if w.getsampwidth() != 2:
            raise ValueError(f"{path}: need 16-bit PCM WAV")
        rate, channels = w.getframerate(), w.getnchannels()
        pcm = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    if channels > 1:
        pcm = pcm.reshape(-1, channels).mean(axis=1)
    if rate != SR:
        from scipy.signal import resample_poly

        g = gcd(SR, rate)
        pcm = resample_poly(pcm, SR // g, rate // g).astype(np.float32)
    return pcm


def enroll(wavs: list[Path], model_path: str, out_path: str) -> Path:
    if not wavs:
        raise ValueError("no enrollment recordings")
    mean = np.mean([embed(load_wav(p), model_path) for p in wavs], axis=0)
    out = _abs(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    np.save(out, mean / (np.linalg.norm(mean) + 1e-9))
    return out


def score(pcm16k: np.ndarray, voiceprint_path: str, model_path: str) -> float:
    enrolled = np.load(_abs(voiceprint_path))
    return float(np.dot(embed(pcm16k, model_path), enrolled))


def score_if_ready(pcm16k: np.ndarray, voiceprint_path: str, model_path: str) -> float | None:
    """None when the model or the voiceprint is missing — the lock fails closed."""
    if not (_abs(voiceprint_path).is_file() and _abs(model_path).is_file()):
        return None
    return score(pcm16k, voiceprint_path, model_path)
