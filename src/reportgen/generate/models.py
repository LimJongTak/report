"""draft.json 구조 (기능정의서 5.2)."""
from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

NEEDS_CHECK_RE = re.compile(r"\[확인 필요[:：]?\s*([^\]]*)\]")


class Source(BaseModel):
    model_config = ConfigDict(extra="ignore")
    file: str = ""
    loc: str = ""
    quote: str = ""


class FieldDraft(BaseModel):
    model_config = ConfigDict(extra="ignore")
    value: Any = ""
    sources: list[Source] = Field(default_factory=list)
    needs_check: list[str] = Field(default_factory=list)
    status: Literal["draft", "edited", "confirmed", "error"] = "draft"
    origin: Literal["data", "ai", "empty", "user"] = "ai"
    type: str = "text"
    error: str = ""


class AIFieldOut(BaseModel):
    """GEN-08 AI 응답 스키마"""
    model_config = ConfigDict(extra="ignore")
    value: Any
    sources: list[Source] = Field(default_factory=list)
    needs_check: list[str] = Field(default_factory=list)


def collect_needs_check(value: Any) -> list[str]:
    """값 안의 [확인 필요: 사유] 목록."""
    out: list[str] = []
    if isinstance(value, str):
        out += [m.group(1).strip() or "확인 필요" for m in NEEDS_CHECK_RE.finditer(value)]
    elif isinstance(value, list):
        for v in value:
            out += collect_needs_check(v)
    elif isinstance(value, dict):
        for v in value.values():
            out += collect_needs_check(v)
    return out
