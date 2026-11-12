import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

TEMPLATE = ROOT / "library" / "templates" / "aiboot_result_v1" / "template.hwpx"


@pytest.fixture
def template_path():
    if not TEMPLATE.exists():
        pytest.skip("기본 양식이 등록되지 않음 (scripts/import_library.py --build-default 실행 필요)")
    return TEMPLATE


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """projects/ 를 임시 폴더로 돌리고 API 키를 끈 상태(오프라인)."""
    from reportgen import config
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(config, "has_api_key", lambda: False)
    orig = config.path

    def fake_path(key):
        return tmp_path / "projects" if key == "projects" else orig(key)
    monkeypatch.setattr(config, "path", fake_path)
    return tmp_path
