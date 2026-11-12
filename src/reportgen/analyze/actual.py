"""실적 구조화 → work/actual.json (GEN-02 / F-09).

AI가 자료에서 사실을 뽑고, 표 자료(설문·명단·지출)는 코드가 직접 집계해 덮어쓴다.
"""
from __future__ import annotations

import json

from .. import config, llm
from ..ingest.base import ExtractedDoc
from ..privacy import Masker
from . import sheets
from .common import docs_to_prompt
from .models import Actual, dump


def code_facts(docs: list[ExtractedDoc]) -> dict:
    """표 자료에서 코드로 계산한 사실(설문·명단·지출)."""
    return {
        "survey": sheets.detect_survey(docs),
        "roster": sheets.detect_roster(docs),
        "budget": sheets.detect_budget(docs),
    }


def build(docs: list[ExtractedDoc], plan: dict, masker: Masker, log_dir=None) -> tuple[dict, dict]:
    """GEN-02 결과자료 → actual dict (+ _code 코드 집계)."""
    facts = code_facts(docs)
    usage: dict = {}
    if docs and config.has_api_key():
        text = docs_to_prompt(docs, masker, int(config.get("ingest.max_excerpt_chars", 60000)))
        plan_brief = {k: plan.get(k) for k in ("사업명", "행사명", "시작일", "종료일", "장소", "대상", "목표인원") if plan.get(k)}
        data, usage = llm.call_json("extract_actual", {
            "documents": text,
            "plan": masker.mask(json.dumps(plan_brief, ensure_ascii=False)),
            "code_facts": json.dumps({k: bool(v) for k, v in facts.items()}, ensure_ascii=False),
        }, Actual, log_dir=log_dir, tag="extract_actual")
        data = masker.unmask_obj(data)
    else:
        data = dump(Actual())
        if docs:
            data["_note"] = "AI 미연결: 표 자료의 코드 집계만 반영"
    data["_code"] = facts
    # 코드 집계값 우선 (절대규칙 1)
    r = facts.get("roster")
    if r:
        data["참여인원"] = r.get("참석인원", r["명단인원"]) if r.get("참석인원") else r["명단인원"]
        data.setdefault("sources", {})["참여인원"] = r["sources"]
    b = facts.get("budget")
    if b:
        data["집행내역"] = b["rows"]
        data.setdefault("sources", {})["집행내역"] = b["sources"]
    return data, usage
