"""friday · tests/unit/test_tools_registry.py

config/tools.py: valid entries load typed, bad entries fail LOUDLY at load —
a typo'd risk level must never silently become an unguarded tool.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from config.tools import load_tools


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "tools.yaml"
    path.write_text(body)
    return path


def test_valid_registry_loads_typed(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "tools:\n"
        "  - name: content_pipeline\n"
        "    description: runs the content pipeline\n"
        "    adapter: adapters.n8n:call\n"
        "    webhook_path: /webhook/content\n"
        "    risk: confirm\n",
    )
    (tool,) = load_tools(path)
    assert tool.name == "content_pipeline"
    assert tool.risk == "confirm"


def test_empty_registry_is_fine(tmp_path: Path) -> None:
    assert load_tools(_write(tmp_path, "tools: []\n")) == []
    assert load_tools(_write(tmp_path, "# comments only\n")) == []


def test_bad_risk_level_fails_loudly(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "tools:\n"
        "  - name: x\n    description: d\n    adapter: a:b\n    risk: yolo\n",
    )
    with pytest.raises(ValidationError):
        load_tools(path)


def test_missing_required_field_fails_loudly(tmp_path: Path) -> None:
    path = _write(tmp_path, "tools:\n  - name: x\n    risk: safe\n")
    with pytest.raises(ValidationError):
        load_tools(path)


def test_real_repo_registry_parses() -> None:
    load_tools()  # the checked-in tools.yaml must always be loadable
