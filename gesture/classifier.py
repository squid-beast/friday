"""friday · gesture/classifier.py

Pure hand-gesture classifier: 2D hand landmarks -> a named static gesture, the
"whole set" — fist, point, sarina's middle finger, pinch, peace, three, four,
open_palm, thumbs_up. No camera, no Vision, no I/O; the native binary feeds the
landmarks (per hand). Motion gestures (swipe/zoom) come later.

Landmarks: {joint_name: (x, y)} normalized (0..1). Thresholds are calibration
knobs — hands and cameras vary. ponytail: tune _EXTEND_RATIO / _PINCH_RATIO live.
"""

from math import hypot

_FINGERS = {  # non-thumb fingers: (tip, pip). "extended" = tip clearly beyond pip.
    "index": ("index_tip", "index_pip"),
    "middle": ("middle_tip", "middle_pip"),
    "ring": ("ring_tip", "ring_pip"),
    "little": ("little_tip", "little_pip"),
}
_EXTEND_RATIO = 1.15  # tip >15% farther from the wrist than the pip
_PINCH_RATIO = 0.35   # thumb tip within 35% of hand-scale of the index tip
_THUMB_OUT = 0.7      # thumb tip this far (x hand-scale) from the index knuckle = out


def _dist(a, b) -> float:
    return hypot(a[0] - b[0], a[1] - b[1])


def _extended(lm: dict, wrist, tip_key: str, pip_key: str) -> bool:
    tip, pip = lm.get(tip_key), lm.get(pip_key)
    if tip is None or pip is None:
        return False
    return _dist(tip, wrist) > _dist(pip, wrist) * _EXTEND_RATIO


def _thumb_out(lm: dict, scale: float) -> bool:
    """Thumb sticking out sideways (best-effort — the thumb is hard in 2D)."""
    tip, index_mcp = lm.get("thumb_tip"), lm.get("index_mcp")
    return tip is not None and index_mcp is not None and _dist(tip, index_mcp) > _THUMB_OUT * scale


def classify(landmarks: dict) -> str:
    """{joint: (x, y)} -> a gesture name, or 'none' for an unrecognized pose."""
    wrist = landmarks.get("wrist")
    if wrist is None:
        return "none"
    scale = _dist(wrist, landmarks.get("middle_mcp", wrist)) or 1.0
    ext = {f: _extended(landmarks, wrist, tip, pip) for f, (tip, pip) in _FINGERS.items()}
    up = {f for f, e in ext.items() if e}
    thumb_out = _thumb_out(landmarks, scale)
    thumb, index_tip = landmarks.get("thumb_tip"), landmarks.get("index_tip")
    pinching = (thumb is not None and index_tip is not None
                and _dist(thumb, index_tip) < _PINCH_RATIO * scale)

    if pinching and (up or thumb_out):  # thumb meets index, hand not a full fist
        return "pinch"
    if not up:
        return "thumbs_up" if thumb_out else "fist"
    if up == {"index"}:
        return "point"
    if up == {"middle"}:
        return "sarina's middle finger"
    if up == {"index", "middle"}:
        return "peace"
    if up == {"index", "middle", "ring"}:
        return "three"
    if up == {"index", "middle", "ring", "little"}:
        return "open_palm" if thumb_out else "four"
    return "none"  # some other partial combo
