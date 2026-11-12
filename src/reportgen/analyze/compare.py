"""계획 대비 실적 (GEN-03 / F-10). 달성률·집행률은 Python으로만 계산한다."""
from __future__ import annotations

from ..generate.formatting import fmt_int, fmt_pct, parse_number, ratio
from . import sheets


def survey_from(actual: dict) -> dict | None:
    """설문: 코드 집계 우선, 없으면 AI가 옮겨 적은 문항별 응답 수를 코드로 다시 계산."""
    code = (actual.get("_code") or {}).get("survey")
    meta = actual.get("만족도") or {}
    if code:
        s = dict(code)
    elif meta.get("문항"):
        items = []
        for it in meta["문항"]:
            counts = [int(parse_number(it.get("응답", {}).get(k)) or 0) for k in sheets.LIKERT]
            if sum(counts):
                items.append(sheets.survey_item_view(it["문항"], counts))
        if not items:
            return None
        s = {"items": items, "응답자수": meta.get("응답자수") or max(i["응답자수"] for i in items),
             "sources": (actual.get("sources") or {}).get("만족도", []), "method": "자료 기재값(코드 재계산)"}
    else:
        return None
    for k in ("조사기간", "조사대상", "조사방법", "활용목적"):
        s[k] = meta.get(k) or s.get(k)
    if meta.get("응답자수") and not code:
        s["응답자수"] = meta["응답자수"]
    s["응답자수_표시"] = f"{fmt_int(s['응답자수'])}명" if s.get("응답자수") else None
    overall = next((i for i in s["items"] if "전반" in i["문항"] or "종합" in i["문항"]), None)
    s["전체긍정률"] = (overall or {}).get("긍정률") if overall else (
        round(sum(i["긍정률"] for i in s["items"]) / len(s["items"]), 1) if s["items"] else None)
    return s


def budget_total(rows: list[dict]) -> float | None:
    vals = [parse_number(r.get("금액")) for r in rows or []]
    vals = [v for v in vals if v is not None]
    return sum(vals) if vals else None


def build(plan: dict, actual: dict) -> dict:
    """GEN-03 비교표. rows: 항목, 계획, 실적, 단위, 달성률, 근거"""
    rows = []

    def add(name, p, a, unit, label="달성률", note=""):
        r = ratio(a, p)
        rows.append({
            "항목": name,
            "계획": f"{fmt_int(p)}{unit}" if p is not None else "-",
            "실적": f"{fmt_int(a)}{unit}" if a is not None else "-",
            "단위": unit,
            "달성률": fmt_pct(r) if r is not None else "-",
            "구분": label,
            "근거": note,
            "_ratio": r,
        })

    p_n, a_n = parse_number(plan.get("목표인원")), parse_number(actual.get("참여인원"))
    if p_n is not None or a_n is not None:
        add("참여인원", p_n, a_n, "명", note="계획안 목표인원 / 결과자료 참여인원")
    p_b, a_b = budget_total(plan.get("예산")), budget_total(actual.get("집행내역"))
    if p_b is not None or a_b is not None:
        add("예산 집행", p_b, a_b, "원", label="집행률", note="계획 예산 합계 / 집행액 합계(코드 합산)")
    p_s, a_s = len(plan.get("세부프로그램") or []), len(actual.get("운영일정") or [])
    if p_s and a_s:
        add("프로그램 운영", p_s, a_s, "개", note="계획 세부프로그램 수 / 실제 운영일정 수")
    s = survey_from(actual)
    target = parse_number(plan.get("만족도목표"))
    if s and s.get("전체긍정률") is not None:
        r = ratio(s["전체긍정률"], target) if target else None
        rows.append({"항목": "만족도(긍정 응답)", "계획": f"{fmt_int(target)}%" if target else "-",
                     "실적": f"{int(s['전체긍정률'])}%", "단위": "%", "달성률": fmt_pct(r) if r else "-",
                     "구분": "달성률", "근거": "만족도 조사(코드 집계)", "_ratio": r})
    return {"rows": rows, "survey": s,
            "budget": {"계획합계": p_b, "집행합계": a_b, "집행률": ratio(a_b, p_b)}}
