"""jarvis-life-os · tests/unit/test_killswitch.py

The testable surface: hotkey parsing and icon truth-table. The rumps UI itself
is exercised live (it needs the macOS run loop).
"""

import pytest

from client.daemon import SessionState
from client.killswitch import _ICONS, parse_hotkey


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        ("cmd+alt+j", "<cmd>+<alt>+j"),
        ("CMD + Opt + J", "<cmd>+<alt>+j"),
        ("option+cmd+j", "<alt>+<cmd>+j"),
        ("ctrl+shift+k", "<ctrl>+<shift>+k"),
        ("j", "j"),
    ],
)
def test_parse_hotkey(spec: str, expected: str) -> None:
    assert parse_hotkey(spec) == expected


def test_parse_hotkey_empty_raises() -> None:
    with pytest.raises(ValueError):
        parse_hotkey("  ")


def test_every_state_has_a_truthful_icon() -> None:
    assert set(_ICONS) == set(SessionState)  # a state without an icon would lie by staleness


def test_hotkey_defaults_off() -> None:
    # Blank default = pynput's global keyboard hook is never started (it cost ~⅛
    # of a core while typing). Menu-bar 😴 + spoken "stand down" remain kill paths.
    from config.settings import Settings

    assert Settings.model_fields["hotkey"].default == ""
