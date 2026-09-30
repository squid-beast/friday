"""jarvis-life-os · gesture/actuator.py

Turn a pointing hand into real cursor moves + clicks via Quartz CGEvent. Moving
the cursor needs no special permission; POSTING a click needs macOS Accessibility
(granted once, on prompt). The coordinate mapping is pure and unit-tested; the
Quartz calls are live-only. This is the ONLY place gestures touch the real Mac —
it runs only while cursor control is explicitly enabled (see gesture/agent.py).
"""

import logging

log = logging.getLogger(__name__)


def to_screen(
    nx: float, ny: float, w: float, h: float, *, mirror: bool = True
) -> tuple[float, float]:
    """Normalized hand point (origin bottom-left) -> screen pixels (origin top-left).
    mirror flips x so moving your hand right moves the cursor right (selfie view)."""
    sx = (1.0 - nx) if mirror else nx
    return sx * w, (1.0 - ny) * h


def _q():
    import Quartz

    return Quartz


def screen_size() -> tuple[float, float]:
    q = _q()
    bounds = q.CGDisplayBounds(q.CGMainDisplayID())
    return bounds.size.width, bounds.size.height


def move(px: float, py: float) -> None:
    """Warp the cursor to a screen point (no permission needed)."""
    _q().CGWarpMouseCursorPosition((px, py))


def click(px: float, py: float) -> None:
    """A left click at a screen point (needs Accessibility permission)."""
    q = _q()
    for event_type in (q.kCGEventLeftMouseDown, q.kCGEventLeftMouseUp):
        event = q.CGEventCreateMouseEvent(None, event_type, (px, py), q.kCGMouseButtonLeft)
        q.CGEventPost(q.kCGHIDEventTap, event)


# G3 keyboard shortcuts (virtual key codes). Needs Accessibility, like clicks.
KEY_LEFT, KEY_RIGHT, KEY_EQUALS, KEY_MINUS = 123, 124, 24, 27


def key(keycode: int, *, cmd: bool = False, ctrl: bool = False, shift: bool = False) -> None:
    q = _q()
    flags = 0
    if cmd:
        flags |= q.kCGEventFlagMaskCommand
    if ctrl:
        flags |= q.kCGEventFlagMaskControl
    if shift:
        flags |= q.kCGEventFlagMaskShift
    for down in (True, False):
        event = q.CGEventCreateKeyboardEvent(None, keycode, down)
        if flags:
            q.CGEventSetFlags(event, flags)
        q.CGEventPost(q.kCGHIDEventTap, event)


def switch_space(direction: str) -> None:
    """Move one desktop/Space left or right (⌃← / ⌃→)."""
    key(KEY_RIGHT if direction == "right" else KEY_LEFT, ctrl=True)


def zoom(direction: str) -> None:
    """Zoom the focused app in or out (Cmd-plus / Cmd-minus)."""
    key(KEY_EQUALS if direction == "in" else KEY_MINUS, cmd=True)
