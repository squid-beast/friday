"""friday · tests/unit/test_launchd.py

 launchd templates: valid plist XML, truthful labels, crash-restart where it
 matters, logs under the external state dir. Installer script must at least parse.
"""

import plistlib
import subprocess
from pathlib import Path

import pytest

_LAUNCHD = Path(__file__).resolve().parents[2] / "launchd"
_PLISTS = sorted(_LAUNCHD.glob("*.plist"))
_ON_DEMAND = sorted((_LAUNCHD / "on-demand").glob("*/*.plist"))  # groups, never auto-installed


def test_all_agents_present() -> None:
    assert [p.name for p in _PLISTS] == [
        "com.friday.checkin.plist",
        "com.friday.dashboard.plist",
        "com.friday.killswitch.plist",
        "com.friday.logrotate.plist",
        "com.friday.metrics.plist",
    ]  # screenpipe+moondream removed, phone voice on-demand (09-29); checkin added (09-30)
    assert [p.relative_to(_LAUNCHD / "on-demand").as_posix() for p in _ON_DEMAND] == [
        "phone/com.friday.livekit.plist", "phone/com.friday.voiceworker.plist",
        "tunnel/com.friday.tunnel.plist"]


@pytest.mark.parametrize("path", _PLISTS + _ON_DEMAND, ids=lambda p: p.stem)
def test_plist_parses_with_label_and_program(path: Path) -> None:
    data = plistlib.loads(path.read_bytes())
    assert data["Label"] == path.stem
    assert data["ProgramArguments"], "empty ProgramArguments would be a silent no-op"
    # scheduled nudges must not fire on every login/reinstall; services + sweeps start at load
    assert data["RunAtLoad"] is ("StartCalendarInterval" not in data)


@pytest.mark.parametrize(
    "stem",
    ["com.friday.killswitch", "com.friday.dashboard"],
)
def test_long_running_agents_crash_restart(stem: str) -> None:
    data = plistlib.loads((_LAUNCHD / f"{stem}.plist").read_bytes())
    assert data["KeepAlive"] is True  # the PLAN's crash-restart guarantee


def test_livekit_retries_only_until_success() -> None:
    livekit = _LAUNCHD / "on-demand" / "phone" / "com.friday.livekit.plist"
    data = plistlib.loads(livekit.read_bytes())
    assert data["KeepAlive"] == {"SuccessfulExit": False}  # retry while Docker warms up


@pytest.mark.parametrize("stem", ["com.friday.metrics", "com.friday.logrotate"])
def test_hourly_timers_are_sweeps_not_daemons(stem: str) -> None:
    data = plistlib.loads((_LAUNCHD / f"{stem}.plist").read_bytes())
    assert data["StartInterval"] == 3600
    assert "KeepAlive" not in data  # a sweep, not a service


@pytest.mark.parametrize("path", _PLISTS + _ON_DEMAND, ids=lambda p: p.stem)
def test_logs_land_under_state_logs(path: Path) -> None:
    data = plistlib.loads(path.read_bytes())
    for key in ("StandardOutPath", "StandardErrorPath"):
        assert data[key].startswith("__STATE__/logs/")


def test_killswitch_runs_healthcheck_first() -> None:
    data = plistlib.loads((_LAUNCHD / "com.friday.killswitch.plist").read_bytes())
    command = " ".join(data["ProgramArguments"])
    assert "healthcheck --quick" in command  # healthcheck-first startup (TESTING.md)
    assert command.index("healthcheck") < command.index("killswitch")


def test_installer_script_parses() -> None:
    script = Path(__file__).resolve().parents[2] / "scripts" / "install_launchd.sh"
    subprocess.run(["bash", "-n", str(script)], check=True, timeout=30)


def test_proactive_checkin_is_a_calendar_nudge_not_a_daemon() -> None:
    data = plistlib.loads((_LAUNCHD / "com.friday.checkin.plist").read_bytes())
    assert [(t["Hour"], t["Minute"]) for t in data["StartCalendarInterval"]] == [
        (9, 0), (13, 0), (19, 0)]
    assert data["RunAtLoad"] is False and "KeepAlive" not in data


def test_tunnel_serves_only_the_dashboard_and_restarts() -> None:
    data = plistlib.loads((_LAUNCHD / "on-demand" / "tunnel" / "com.friday.tunnel.plist")
                          .read_bytes())
    assert data["ProgramArguments"][0] == "__CLOUDFLARED__"
    assert data["ProgramArguments"][-2:] == ["run", "friday"]
    assert data["KeepAlive"] is True
    example = (_LAUNCHD.parent / "deploy" / "cloudflared-config.example.yml").read_text()
    assert "service: http://127.0.0.1:8787" in example and "http_status:404" in example
