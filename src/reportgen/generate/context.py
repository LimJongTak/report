"""필드별 컨텍스트 조립 (GEN-04 / F-11).

- data_context(): 코드가 채울 값(plan/actual/comparison/survey/budget/calc/photos)
- resolve(): schema의 binding 경로로 값 찾기
- ai_context(): AI 필드용 프롬프트 변수(문체 프로필, 과거 예시, 사실 자료, 원문 발췌)
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .. import config, ingest
from ..analyze import compare
from ..library import examples, style
from ..privacy import Masker
from ..project import Project
from ..render.charts import likert_bar
from .formatting import fmt_date_range, fmt_int, fmt_money, parse_number


def _title(name: str) -> str:
    name = (name or "").strip()
    name = re.sub(r"\s*결과\s*보고(서)?$", "", name)
    return f"{name}\n결과보고" if len(name) > 16 else f"{name} 결과보고"


def selected_photos(project: Project) -> list[str]:
    sel = project.meta.get("photos")
    photos = project.photos()
    if sel is None:
        def taken(p: Path):
            j = project.extracted_dir / f"{p.name}.json"
            if j.exists():
                return json.loads(j.read_text(encoding="utf-8")).get("meta", {}).get("taken") or p.name
            return p.name
        return [str(p) for p in sorted(photos, key=taken)[:8]]
    names = {p.name: p for p in photos}
    return [str(names[n]) for n in sel if n in names]


def data_context(project: Project) -> dict:
    plan = project.read_json("plan.json", {}) or {}
    actual = project.read_json("actual.json", {}) or {}
    cmp_ = project.read_json("comparison.json") or compare.build(plan, actual)
    survey = cmp_.get("survey")
    if survey:
        for i, it in enumerate(survey["items"]):
            path = project.work / "charts" / f"q{i + 1}.png"
            if not path.exists():
                likert_bar(it, path)
            it["차트"] = str(path)
    budget_rows = [
        {"예산과목": r.get("예산과목", ""), "세부항목": r.get("세부항목", ""), "산출내역": r.get("산출내역", ""),
         "금액": fmt_money(r.get("금액"))}
        for r in (actual.get("집행내역") or [])
    ]
    total = compare.budget_total(actual.get("집행내역"))
    n = parse_number(actual.get("참여인원"))
    calc = {
        "보고서제목": _title(actual.get("행사명") or plan.get("행사명") or plan.get("사업명") or project.meta.get("name", "")),
        "행사일시": fmt_date_range(actual.get("시작일") or plan.get("시작일"), actual.get("종료일") or plan.get("종료일"),
                               actual.get("시간") or plan.get("시간")) if (actual.get("시작일") or plan.get("시작일")) else None,
        "참여인원": n,
        "참여인원_표시": f"{fmt_int(n)}명" if n is not None else None,
        "집행총액": total,
        "집행총액_표시": fmt_money(total) if total is not None else None,
    }
    return {
        "plan": plan, "actual": actual,
        "comparison": {"rows": [{k: v for k, v in r.items() if not k.startswith("_")} for r in cmp_.get("rows", [])]},
        "survey": survey or {}, "budget": {"rows": budget_rows}, "calc": calc,
        "photos": selected_photos(project),
    }


def _get(obj: Any, path: str) -> Any:
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list) and part.isdigit():
            i = int(part)
            cur = cur[i] if i < len(cur) else None
        else:
            return None
        if cur is None:
            return None
    return cur


def _empty(v: Any) -> bool:
    return v is None or v == "" or v == [] or v == {}


def resolve(binding: str | None, ctx: dict) -> tuple[Any, list[dict], str]:
    """binding 'a.b|c.d' → (값, 근거, 사용한 경로)"""
    if not binding:
        return None, [], ""
    for path in binding.split("|"):
        path = path.strip()
        v = _get(ctx, path)
        if not _empty(v):
            return v, _sources_for(path, ctx), path
    return None, [], ""


def _sources_for(path: str, ctx: dict) -> list[dict]:
    root, _, rest = path.partition(".")
    key = rest.split(".")[0]
    if root in ("plan", "actual"):
        return list((ctx[root].get("sources") or {}).get(key, [])) or [{"file": f"{root}.json", "loc": key, "quote": ""}]
    if root == "survey":
        return ctx["survey"].get("sources", [])
    if root == "budget":
        return (ctx["actual"].get("sources") or {}).get("집행내역", []) or [{"file": "actual.json", "loc": "집행내역", "quote": ""}]
    if root == "photos":
        return [{"file": Path(_get(ctx, path) or "").name, "loc": "사진", "quote": ""}]
    return [{"file": "코드 계산", "loc": path, "quote": ""}]


def facts_summary(ctx: dict) -> dict:
    """AI에 넘길 사실 자료(숫자는 이미 코드로 계산된 값)."""
    plan = {k: v for k, v in ctx["plan"].items() if k not in ("sources",) and not k.startswith("_")}
    actual = {k: v for k, v in ctx["actual"].items() if k not in ("sources",) and not k.startswith("_")}
    survey = ctx.get("survey") or {}
    return {
        "계획": plan,
        "실적": actual,
        "계획대비실적": ctx["comparison"]["rows"],
        "만족도": {k: v for k, v in survey.items() if k not in ("items", "sources")} | {
            "문항": [{"문항": i["문항"], "요약수치": i["요약수치"]} for i in survey.get("items", [])]} if survey else None,
        "코드계산": {k: v for k, v in ctx["calc"].items() if v is not None},
    }


def documents_excerpt(project: Project, masker: Masker, max_chars: int | None = None) -> str:
    from ..analyze.common import docs_to_prompt
    docs = ingest.load_extracted(project.extracted_dir)
    docs = [d for d in docs if d.type != "image"]
    return docs_to_prompt(docs, masker, max_chars or int(config.get("ingest.max_excerpt_chars", 60000)))


def ai_variables(field: dict, ctx: dict, project: Project, masker: Masker, instruction: str = "",
                 docs_text: str | None = None) -> dict:
    """GEN-04 필드 1개 생성용 변수."""
    event_type = examples.classify(project.meta.get("name", ""))
    exs = examples.snippets(field["key"], event_type, n=3)
    spec = {k: field.get(k) for k in ("key", "type", "guide", "max_chars", "columns", "ai_subfields", "source_hint") if field.get(k)}
    return {
        "field_key": field["key"],
        "field_spec": json.dumps(spec, ensure_ascii=False),
        "style_profile": style.load()[:6000],
        "examples": "\n\n".join(f"--- 예시 {i + 1} ({e['example']}, {e['type']}) ---\n{e['text']}" for i, e in enumerate(exs)) or "(등록된 예시 없음)",
        "facts": masker.mask(json.dumps(facts_summary(ctx), ensure_ascii=False, indent=1, default=str)),
        "documents": docs_text if docs_text is not None else documents_excerpt(project, masker),
        "instruction": instruction or "(없음)",
        "project_name": project.meta.get("name", ""),
    }
