"""검증 (VAL-02~05 / F-13).

- 숫자 근거: 초안의 모든 숫자가 추출 원문·계산값(plan/actual/comparison)에 있는지
- 합계: 예산 표 합계 = 예산합계/예산총액, 설문 문항 응답 합 = 응답자수
- 필수 필드 비어있음, [확인 필요] 개수, 미치환 {{ }}
"""
from __future__ import annotations

import json
import re
from typing import Any

from .. import ingest
from ..generate.formatting import parse_number
from ..generate.models import collect_needs_check
from ..library import templates
from ..project import Project

NUM_RE = re.compile(r"(?<![\w.])\d{1,3}(?:,\d{3})+(?:\.\d+)?|(?<![\w.,])\d+(?:\.\d+)?")
# 날짜·연도·순번처럼 근거 확인이 의미 없는 숫자
TRIVIAL = {str(i) for i in range(0, 11)}


def _numbers(text: str) -> list[str]:
    out = []
    for m in NUM_RE.finditer(text):
        s = m.group()
        if s in TRIVIAL:
            continue
        out.append(s)
    return out


def _norm(s: str) -> str:
    n = parse_number(s)
    if n is None:
        return s
    return str(int(n)) if float(n).is_integer() else str(round(n, 2))


def _flatten(v: Any) -> str:
    if isinstance(v, str):
        return v
    if isinstance(v, list):
        return "\n".join(_flatten(x) for x in v)
    if isinstance(v, dict):
        return "\n".join(_flatten(x) for k, x in v.items() if k != "차트")
    return "" if v is None else str(v)


def evidence_numbers(project: Project) -> set[str]:
    """근거로 인정되는 숫자 집합: 추출 원문 + 구조화/계산 결과."""
    texts = [d.to_markdown() for d in ingest.load_extracted(project.extracted_dir)]
    for name in ("plan.json", "actual.json", "comparison.json"):
        texts.append(json.dumps(project.read_json(name, {}), ensure_ascii=False, default=str))
    texts.append(project.meta.get("date", "") + " " + project.meta.get("name", ""))
    nums = set()
    for t in texts:
        for s in _numbers(t):
            nums.add(_norm(s))
        # 날짜 구성요소(2026-07-10 → 2026, 7, 10, 07)
        for y, m, d in re.findall(r"(20\d{2})\D{1,3}(\d{1,2})\D{1,3}(\d{1,2})", t):
            nums |= {y, str(int(m)), str(int(d))}
    return nums


def run(project: Project, draft: dict | None = None, rendered_remaining: list[str] | None = None) -> dict:
    """VAL-02~04 검증 실행 → validation.json"""
    from ..generate.drafter import load_draft
    draft = draft or load_draft(project)
    schema = templates.load_schema(project.meta["template_id"])
    fields = draft.get("fields", {})
    evid = evidence_numbers(project)
    issues: list[dict] = []
    per_field: dict[str, dict] = {}

    for f in schema["fields"]:
        key = f["key"]
        fd = fields.get(key, {})
        v = fd.get("value", "")
        text = _flatten(v)
        fi = {"unsupported_numbers": [], "needs_check": collect_needs_check(v), "empty": False}
        if f.get("required", True) and f.get("type") != "image" and not text.strip():
            fi["empty"] = True
            issues.append({"level": "error", "field": key, "kind": "필수 필드 비어있음", "detail": ""})
        if fd.get("status") == "error":
            issues.append({"level": "error", "field": key, "kind": "생성 실패", "detail": fd.get("error", "")})
        if f.get("type") != "image":
            for s in _numbers(re.sub(r"\[확인 필요[^\]]*\]", "", text)):
                if _norm(s) not in evid:
                    fi["unsupported_numbers"].append(s)
            if fi["unsupported_numbers"]:
                issues.append({"level": "warn", "field": key, "kind": "근거 없는 숫자",
                               "detail": ", ".join(dict.fromkeys(fi["unsupported_numbers"]))})
        for r in fi["needs_check"]:
            issues.append({"level": "warn", "field": key, "kind": "확인 필요", "detail": r})
        if re.search(r"\{\{[^}]+\}\}", text):
            issues.append({"level": "error", "field": key, "kind": "값 안에 {{ }} 남음", "detail": ""})
        per_field[key] = fi

    # VAL-04 합계 검증
    rows = fields.get("예산집행내역", {}).get("value") or []
    if isinstance(rows, list) and rows:
        s = sum(parse_number(r.get("금액")) or 0 for r in rows if isinstance(r, dict))
        for k in ("예산합계", "예산총액"):
            if k in fields:
                t = parse_number(fields[k].get("value"))
                if t is not None and abs(t - s) >= 1:
                    issues.append({"level": "error", "field": k, "kind": "합계 불일치",
                                   "detail": f"표 금액 합 {int(s):,} ≠ {k} {int(t):,}"})
    actual = project.read_json("actual.json", {}) or {}
    b = (actual.get("_code") or {}).get("budget")
    if b and not b.get("합계일치", True):
        issues.append({"level": "warn", "field": "예산집행내역", "kind": "원자료 합계 불일치",
                       "detail": f"지출표에 적힌 합계 {b.get('표기합계'):,.0f} ≠ 항목 합 {b.get('합계'):,.0f} ({b['sources'][0]['file']})"})
    items = fields.get("만족도문항", {}).get("value") or []
    resp = parse_number(fields.get("응답자수", {}).get("value"))
    if isinstance(items, list) and resp:
        for it in items:
            if not isinstance(it, dict):
                continue
            nums = [parse_number(x) for x in re.findall(r":\s*(\d+)", str(it.get("응답분포", "")))]
            if nums and sum(n or 0 for n in nums) > resp:
                issues.append({"level": "warn", "field": "만족도문항", "kind": "응답 수 초과",
                               "detail": f"'{it.get('문항')}' 응답 합 {int(sum(nums))} > 응답자 {int(resp)}"})
    plan = project.read_json("plan.json", {}) or {}
    n_act = parse_number(actual.get("참여인원"))
    n_goal = parse_number(plan.get("목표인원"))
    if n_act is not None and resp and resp > n_act:
        issues.append({"level": "warn", "field": "응답자수", "kind": "응답자 > 참여인원",
                       "detail": f"응답자 {int(resp)}명 > 참여인원 {int(n_act)}명"})
    if n_goal is None and "참여인원" in fields:
        issues.append({"level": "info", "field": "계획대비실적", "kind": "목표인원 없음",
                       "detail": "계획안에서 목표인원을 찾지 못해 달성률을 계산하지 않았습니다"})
    for m in rendered_remaining or []:
        issues.append({"level": "error", "field": "(출력물)", "kind": "미치환 필드", "detail": m})

    summary = {
        "errors": sum(1 for i in issues if i["level"] == "error"),
        "warnings": sum(1 for i in issues if i["level"] == "warn"),
        "needs_check": sum(len(v["needs_check"]) for v in per_field.values()),
        "unsupported_numbers": sum(len(v["unsupported_numbers"]) for v in per_field.values()),
        "empty_required": sum(1 for v in per_field.values() if v["empty"]),
    }
    result = {"summary": summary, "issues": issues, "fields": per_field}
    project.write_json("validation.json", result)
    return result
