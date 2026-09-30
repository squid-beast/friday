"""friday · tests/unit/test_install_launchd.py

The installer's behaviour, run for real against a fake HOME with stub
`launchctl`/`docker` on PATH: the core install never loads on-demand groups,
a group can be switched on AND off on its own (phone-voice-off also stops the
LiveKit container), --uninstall clears everything, unknown groups fail loudly.
"""

import os
import subprocess
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "install_launchd.sh"
_CORE = {"com.friday.checkin.plist", "com.friday.dashboard.plist", "com.friday.killswitch.plist",
         "com.friday.logrotate.plist", "com.friday.metrics.plist"}
_PHONE = {"com.friday.livekit.plist", "com.friday.voiceworker.plist"}


@pytest.fixture
def home(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for tool in ("launchctl", "docker"):  # record every call, never touch the real Mac
        stub = bin_dir / tool
        stub.write_text(f'#!/bin/sh\necho "{tool} $*" >> "{tmp_path}/calls.log"\n')
        stub.chmod(0o755)
    return tmp_path


def _run(home: Path, *args: str, **env: str) -> subprocess.CompletedProcess:
    base = {k: v for k, v in os.environ.items() if k not in ("ON_DEMAND", "ON_DEMAND_OFF")}
    full = {**base, "HOME": str(home), "FRIDAY_STATE_DIR": str(home / "state"),
            "PATH": f"{home / 'bin'}:{os.environ['PATH']}", **env}
    return subprocess.run(["bash", str(_SCRIPT), *args], env=full,
                          capture_output=True, text=True, check=False)


def _installed(home: Path) -> set[str]:
    agents = home / "Library" / "LaunchAgents"
    return {p.name for p in agents.glob("*.plist")} if agents.exists() else set()


def _calls(home: Path) -> str:
    log = home / "calls.log"
    return log.read_text() if log.exists() else ""


def test_core_install_never_loads_on_demand_groups(home: Path) -> None:
    assert _run(home).returncode == 0
    assert _installed(home) == _CORE
    rendered = (home / "Library/LaunchAgents/com.friday.dashboard.plist").read_text()
    assert "__REPO__" not in rendered and "__STATE__" not in rendered


def test_phone_voice_switches_on_and_off_on_its_own(home: Path) -> None:
    _run(home)
    assert _run(home, ON_DEMAND="phone").returncode == 0
    assert _installed(home) == _CORE | _PHONE
    assert _run(home, ON_DEMAND_OFF="phone").returncode == 0
    assert _installed(home) == _CORE  # core untouched by the off switch
    assert "docker compose down" in _calls(home)  # the container can't outlive its agent


def test_uninstall_clears_core_and_every_group(home: Path) -> None:
    _run(home)
    _run(home, ON_DEMAND="phone")
    assert _run(home, "--uninstall").returncode == 0
    assert _installed(home) == set()


def test_unknown_group_fails_loudly(home: Path) -> None:
    result = _run(home, ON_DEMAND="nope")
    assert result.returncode != 0 and "unknown on-demand group" in result.stderr
    assert _installed(home) == set()


def test_tunnel_group_is_independent_of_core_and_phone(home: Path) -> None:
    _run(home)
    assert _run(home, ON_DEMAND="tunnel").returncode == 0
    assert _installed(home) == _CORE | {"com.friday.tunnel.plist"}
    rendered = (home / "Library/LaunchAgents/com.friday.tunnel.plist").read_text()
    assert "__CLOUDFLARED__" not in rendered and "__HOME__" not in rendered
    assert _run(home, ON_DEMAND_OFF="tunnel").returncode == 0
    assert _installed(home) == _CORE
    assert "docker compose down" not in _calls(home)  # only phone-off stops the container
