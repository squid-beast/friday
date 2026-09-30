"""friday · voice/owner_lock.py

The per-turn owner-voice lock (Phase 5). The voice agent tees every audio frame
of the turn into feed(); before the brain runs, verdict(take()) scores the
turn's VOICED audio against sir's enrolled voiceprint (adapters/voiceprint.py):
  owner -> proceed · stranger -> polite refusal · too_short -> ask again ·
  unavailable (no model/voiceprint, or scoring failed) -> refuse: FAIL CLOSED ·
  unlocked (VOICE_LOCK_TURNS off) -> today's behaviour, nothing is scored.
Capability-reducing kill intents are handled before this gate (any voice).
"""

import logging
from collections import deque
from math import gcd

import numpy as np

from adapters import voiceprint

log = logging.getLogger(__name__)

SR = 16_000
MIN_VOICED_S = 0.8  # less voice than this can't be judged reliably
MAX_BUFFER_S = 15.0
REFUSALS = {
    "stranger": "I only take instructions from sir.",
    "too_short": "I didn't catch enough of your voice, sir — once more, a little longer; "
                 "'yes, go ahead' works.",
    "unavailable": "My voice lock can't verify you right now, sir, so I'm holding still.",
}


class OwnerLock:
    def __init__(self, *, armed: bool, score, threshold: float,
                 min_voiced_s: float = MIN_VOICED_S) -> None:
        self.armed = armed
        self._score = score  # pcm16k -> cosine similarity, or None if unavailable
        self._threshold = threshold
        self._min_voiced = int(min_voiced_s * SR)
        self._chunks: deque[tuple[np.ndarray, int]] = deque()
        self._samples = 0

    def feed(self, data: bytes, *, sample_rate: int, channels: int) -> None:
        """One raw int16 frame of the current turn (cheap: just buffered)."""
        pcm = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
        if channels > 1:
            pcm = pcm.reshape(-1, channels).mean(axis=1)
        self._chunks.append((pcm, sample_rate))
        self._samples += len(pcm)
        while self._samples > MAX_BUFFER_S * sample_rate and len(self._chunks) > 1:
            self._samples -= len(self._chunks.popleft()[0])

    def take(self) -> np.ndarray:
        """This turn's audio as 16kHz float32 mono; the buffer starts empty again."""
        chunks, self._chunks, self._samples = list(self._chunks), deque(), 0
        if not chunks:
            return np.zeros(0, np.float32)
        rate = chunks[0][1]
        pcm = np.concatenate([c for c, _ in chunks])
        if rate != SR:
            from scipy.signal import resample_poly

            g = gcd(SR, rate)
            pcm = resample_poly(pcm, SR // g, rate // g).astype(np.float32)
        return pcm

    def verdict(self, pcm: np.ndarray) -> str:
        if not self.armed:
            return "unlocked"
        voiced = voiceprint.voiced(pcm)
        if len(voiced) < self._min_voiced:
            return "too_short"
        try:
            similarity = self._score(voiced)
        except Exception:
            log.warning("owner-voice scoring failed — failing closed", exc_info=True)
            return "unavailable"
        if similarity is None:
            return "unavailable"
        return "owner" if similarity >= self._threshold else "stranger"

    @classmethod
    def from_settings(cls) -> "OwnerLock":
        from config.settings import get_settings

        s = get_settings()
        return cls(armed=s.voice_lock_turns, threshold=s.voiceprint_threshold,
                   score=lambda pcm: voiceprint.score_if_ready(
                       pcm, s.voiceprint_path, s.voiceprint_model_path))
