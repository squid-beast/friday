"""jarvis-life-os · tests/unit/test_jobs.py

Jobs command center: reading batches, decisions round-trip (atomic, audited),
answers, the tracker pipeline, the open-file allowlist, and the HTTP surface.
Everything runs against a fake ~/Downloads/Jobs in tmp_path.
"""

import json
from pathlib import Path

import pytest

from config.settings import get_settings
from integrations import jobs, jobs_actions, jobs_api

BATCH = "2026-09-28"
ROLES = [
    {"n": 1, "key": "acme-swe", "company": "Acme", "role": "SWE", "tier": "mid",
     "submit_mode": "claude", "needs": ["Travel %?"], "consents": [], "folder": "01_Acme_SWE"},
    {"n": 2, "key": "bolt-fde", "company": "Bolt", "role": "FDE", "tier": "startup",
     "submit_mode": "leo", "needs": [], "consents": [], "folder": "02_Bolt_FDE"},
]
TRACKER = """# Targets

## Tracker
| Company | Role | Date | Status | Notes |
|---|---|---|---|---|
| Acme | SWE | 2026-09-27 | prepared | batch |
| Bolt | FDE | 2026-09-26 | applied | batch |
| Cora | AI | 2026-09-25 | rejected | batch |
"""


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "Jobs"
    (root / "_engine" / "state").mkdir(parents=True)
    batch = root / BATCH
    for role in ROLES:
        (batch / role["folder"]).mkdir(parents=True)
    (batch / "01_Acme_SWE" / "Leo_Resume.pdf").write_bytes(b"%PDF")
    (batch / "batch.json").write_text(json.dumps(ROLES))
    (root / "not-a-batch").mkdir()
    vault = tmp_path / "vault"
    (vault / "areas" / "career").mkdir(parents=True)
    (vault / "areas" / "career" / "target-companies.md").write_text(TRACKER)
    monkeypatch.setenv("JOBS_DIR", str(root))
    monkeypatch.setenv("VAULT_PATH", str(vault))
    monkeypatch.setattr(jobs_actions, "log_tool", lambda *a, **k: None)
    jobs._cache.clear()
    get_settings.cache_clear()
    yield root
    get_settings.cache_clear()


def test_batches_and_roles_merge_decisions(home: Path) -> None:
    assert jobs.batches() == [BATCH]
    items = jobs.roles(BATCH)
    assert [i["company"] for i in items] == ["Acme", "Bolt"]
    assert items[0]["decision"] == "" and items[0]["files"]["resume"] is True
    assert items[1]["files"]["cover"] is False


def test_decide_round_trip_is_atomic_and_readable(home: Path) -> None:
    jobs_actions.decide(BATCH, 1, "approve")
    jobs_actions.decide(BATCH, 2, "skip")
    saved = json.loads((home / "_engine" / "state" / f"decisions_{BATCH}.json").read_text())
    assert saved["1"]["decision"] == "approve" and saved["2"]["decision"] == "skip"
    assert not list((home / "_engine" / "state").glob(".decisions-*"))
    summary = jobs.summarize(jobs.roles(BATCH))
    assert summary["approved"] == 1 and summary["skipped"] == 1 and summary["undecided"] == 0


def test_answers_save_clear_and_keep_decision(home: Path) -> None:
    jobs_actions.decide(BATCH, 1, "approve")
    jobs_actions.answer(BATCH, 1, "Travel %?", "Anywhere, 100%")
    item = jobs.roles(BATCH)[0]
    assert item["answers"] == {"Travel %?": "Anywhere, 100%"} and item["decision"] == "approve"
    jobs_actions.answer(BATCH, 1, "Travel %?", "")
    assert jobs.roles(BATCH)[0]["answers"] == {}


@pytest.mark.parametrize("bad", ["../etc", "2026-9-28", "", "2026-09-28/../x"])
def test_bad_batch_names_are_refused(home: Path, bad: str) -> None:
    with pytest.raises(ValueError):
        jobs_actions.decide(bad, 1, "approve")


def test_unknown_role_and_decision_are_refused(home: Path) -> None:
    with pytest.raises(ValueError):
        jobs_actions.decide(BATCH, 99, "approve")
    with pytest.raises(ValueError):
        jobs_actions.decide(BATCH, 1, "submit-now")
    with pytest.raises(ValueError):
        jobs_actions.answer(BATCH, 1, "Q", "x" * (jobs_actions.MAX_ANSWER + 1))


def test_pipeline_counts_tracker_statuses(home: Path) -> None:
    pipe = jobs.pipeline()
    assert pipe["total"] == 3
    assert pipe["by_status"] == {"prepared": 1, "applied": 1, "rejected": 1}
    assert pipe["recent"][0]["company"] == "Cora"


def test_open_file_only_inside_jobs_folder(home: Path) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd, **_kw):
        calls.append(cmd)
        return type("R", (), {"returncode": 0, "stderr": ""})()

    jobs_actions.open_file(BATCH, 1, "resume", run=fake_run)
    assert calls[-1][0] == "open" and calls[-1][1].endswith("Leo_Resume.pdf")
    with pytest.raises(ValueError):
        jobs_actions.open_file(BATCH, 2, "cover", run=fake_run)  # no such file
    with pytest.raises(ValueError):
        jobs_actions.open_file(BATCH, 1, "../../secret", run=fake_run)


def test_api_surface_and_overview(home: Path) -> None:
    jobs_api.decide({"batch": BATCH, "n": "1", "decision": "approve"})
    view = jobs_api.overview({})
    assert view["latest"] == BATCH and view["summary"]["approved"] == 1
    assert view["pipeline"]["total"] == 3 and view["code_queue"] == 0
    detail = jobs_api.batch({})
    assert detail["batch"] == BATCH and len(detail["roles"]) == 2
    with pytest.raises(ValueError):
        jobs_api.decide({"batch": BATCH, "decision": "approve"})


def test_missing_folder_is_empty_not_an_error(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBS_DIR", str(tmp_path / "nope"))
    get_settings.cache_clear()
    jobs._cache.clear()
    assert jobs.overview()["latest"] == "" and jobs.overview()["summary"]["total"] == 0
    get_settings.cache_clear()
