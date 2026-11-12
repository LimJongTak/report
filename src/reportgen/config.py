"""설정 로딩 (NFR-01, NFR-07).

- config/settings.yaml : 모델명, 토큰, 경로 등
- .env                  : 비밀값(ANTHROPIC_API_KEY)
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def settings() -> dict[str, Any]:
    """NFR-07 설정 파일 로딩. .env도 함께 읽는다."""
    load_dotenv(ROOT / ".env")
    with open(ROOT / "config" / "settings.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get(path: str, default: Any = None) -> Any:
    """'llm.model' 같은 점 경로로 설정값 조회."""
    cur: Any = settings()
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def path(key: str) -> Path:
    """paths.* 설정을 프로젝트 루트 기준 절대경로로."""
    p = Path(get(f"paths.{key}", key))
    return p if p.is_absolute() else ROOT / p


def has_api_key() -> bool:
    settings()
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
