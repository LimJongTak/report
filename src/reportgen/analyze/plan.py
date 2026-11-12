"""계획 구조화 → work/plan.json (GEN-01 / F-08).

AI가 계획안 사실을 구조화하고, 예산 표·목표인원처럼 코드로 읽을 수 있는 숫자는 코드 값으로 덮어쓴다.
"""
from __future__ import annotations

import re

from .. import config, llm
from ..generate.formatting import parse_number
from ..ingest.base import ExtractedDoc
from ..privacy import Masker
from . import sheets
from .common import docs_to_prompt
from .models import Plan, dump

GOAL_RE = re.compile(r"(?:목표|모집|정원|예정)\s*(?:인원)?\s*[:：]?\s*(?:총\s*)?(\d{1,4})\s*명|(\d{1,4})\s*명\s*(?:목표|모집|내외)")


def code_facts(docs: list[ExtractedDoc]) -> dict:
    facts: dict = {}
    b = sheets.detect_budget(docs, prefer="금액")
    if b:
        facts["예산"] = b
    sc = sheets.detect_schedule(docs)
    if sc:
        facts["세부프로그램"] = sc
    for d in docs:
        m = GOAL_RE.search(d.text())
        if m:
            facts["목표인원"] = {"value": int(m.group(1) or m.group(2)),
                              "sources": [{"file": d.file, "loc": "본문", "quote": m.group(0)}]}
            break
    return facts


def build(docs: list[ExtractedDoc], masker: Masker, log_dir=None, project_name: str = "") -> tuple[dict, dict]:
    """GEN-01 계획안 → plan dict. 반환 (plan, usage)."""
    if not docs:
        return dump(Plan(사업명=project_name or None)), {}
    usage: dict = {}
    if config.has_api_key():
        text = docs_to_prompt(docs, masker, int(config.get("ingest.max_excerpt_chars", 60000)))
        data, usage = llm.call_json("extract_plan", {"documents": text, "project_name": project_name},
                                    Plan, log_dir=log_dir, tag="extract_plan")
        data = masker.unmask_obj(data)
    else:
        data = {**dump(Plan(사업명=project_name or None)), "_note": "AI 미연결: 표·숫자만 코드로 추출"}
    facts = code_facts(docs)
    data["_code"] = {k: v for k, v in facts.items()}
    if "예산" in facts:
        data["예산"] = facts["예산"]["rows"]
        data.setdefault("sources", {})["예산"] = facts["예산"]["sources"]
    if "세부프로그램" in facts and not data.get("세부프로그램"):
        data["세부프로그램"] = facts["세부프로그램"]["rows"]
        data.setdefault("sources", {})["세부프로그램"] = facts["세부프로그램"]["sources"]
    if "목표인원" in facts and parse_number(data.get("목표인원")) is None:
        data["목표인원"] = facts["목표인원"]["value"]
        data.setdefault("sources", {})["목표인원"] = facts["목표인원"]["sources"]
    return data, usage
