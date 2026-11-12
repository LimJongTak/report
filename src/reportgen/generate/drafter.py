"""초안 생성 (GEN-04~09 / F-11, F-12).

- binding이 있는 필드는 코드가 데이터로 채움(숫자·표·사진)
- 나머지는 필드 단위로 Claude 호출(동시 3개), 결과는 draft.json에 즉시 저장 → 중단돼도 이어서 가능
- AI 출력 JSON: {value, sources, needs_check}. 근거 없는 내용은 [확인 필요: 사유]
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from typing import Any, Callable

from .. import config, llm
from ..library import templates
from ..privacy import Masker, NoMasker
from ..project import Project
from . import context
from .formatting import fmt_money, normalize_text
from .models import AIFieldOut, FieldDraft, collect_needs_check

NO_AI = "[확인 필요: AI 미연결 — 직접 작성하거나 .env에 API 키를 넣고 재생성]"


def masker_for(project: Project) -> Masker:
    if project.meta.get("mask", True):
        return Masker(project.work / "mask_table.json")
    return NoMasker()


def load_draft(project: Project) -> dict:
    return project.read_json("draft.json", {"fields": {}}) or {"fields": {}}


def save_field(project: Project, key: str, fd: FieldDraft, lock: Lock | None = None) -> None:
    def _do():
        d = load_draft(project)
        d["fields"][key] = fd.model_dump()
        project.write_json("draft.json", d)
    if lock:
        with lock:
            _do()
    else:
        _do()


# ---------- 데이터 필드 ----------

def _format_rows(rows: list, columns: list[str] | None) -> list[dict]:
    out = []
    for r in rows:
        if hasattr(r, "model_dump"):
            r = r.model_dump()
        if not isinstance(r, dict):
            r = {"값": r}
        row = {}
        for c in columns or list(r.keys()):
            v = r.get(c, "")
            if c in ("금액", "계획액", "집행액") and v not in ("", None):
                v = fmt_money(v)
            row[c] = "" if v is None else str(v)
        out.append(row)
    return out


def data_field(field: dict, ctx: dict) -> FieldDraft | None:
    value, sources, path = context.resolve(field.get("binding"), ctx)
    if value is None:
        return None
    t = field.get("type", "text")
    if t == "table":
        value = _format_rows(value, field.get("columns"))
        # 같은 날짜 반복은 첫 행만 표시(운영일정 관례)
        if field.get("columns") and field["columns"][0] == "날짜":
            prev = None
            for r in value:
                if r["날짜"] == prev:
                    r["날짜"] = ""
                else:
                    prev = r["날짜"]
    elif t == "block":
        cols = field.get("columns") or []
        value = [{c: it.get(c, "") for c in cols} for it in value]
    elif t == "image":
        value = str(value)
    elif isinstance(value, list):
        value = "\n".join(str(x) for x in value)
    elif isinstance(value, float) and value.is_integer():
        value = str(int(value))
    return FieldDraft(value=value, sources=sources, origin="data", type=t,
                      needs_check=collect_needs_check(value))


# ---------- AI 필드 ----------

def ai_field(field: dict, ctx: dict, project: Project, masker: Masker, instruction: str = "",
             docs_text: str | None = None, base_items: list | None = None) -> FieldDraft:
    t = field.get("type", "text")
    if not config.has_api_key():
        if t == "block" and base_items:
            subs = field.get("ai_subfields") or []
            return FieldDraft(value=[{**it, **{s: NO_AI for s in subs}} for it in base_items], origin="ai", type=t,
                              needs_check=["AI 미연결"])
        if t in ("table", "block"):
            return FieldDraft(value=[], origin="empty", type=t, needs_check=["AI 미연결"])
        return FieldDraft(value=NO_AI, origin="empty", type=t, needs_check=["AI 미연결"])
    variables = context.ai_variables(field, ctx, project, masker, instruction, docs_text)
    if base_items is not None:
        variables["items"] = masker.mask(json.dumps(
            [{k: v for k, v in it.items() if k != "차트"} for it in base_items], ensure_ascii=False, indent=1))
        prompt = "draft_block"
    else:
        variables["items"] = ""
        prompt = "draft_field"
    data, _ = llm.call_json(prompt, variables, AIFieldOut, log_dir=project.logs_dir, tag=f"draft_{field['key']}")
    data = masker.unmask_obj(data)
    value = data["value"]
    if base_items is not None:
        subs = field.get("ai_subfields") or []
        got = value if isinstance(value, list) else []
        value = [{**it, **{s: normalize_text(str((got[i] if i < len(got) else {}).get(s, "[확인 필요: 생성 누락]"))) for s in subs}}
                 for i, it in enumerate(base_items)]
    elif isinstance(value, str):
        value = normalize_text(value.strip())
    elif isinstance(value, list) and t in ("table", "block"):
        value = [{k: normalize_text(str(v)) for k, v in (r.items() if isinstance(r, dict) else {"값": r}.items())} for r in value]
    elif isinstance(value, list):
        value = "\n".join(normalize_text(str(x)) for x in value)
    needs = list(dict.fromkeys(data.get("needs_check", []) + collect_needs_check(value)))
    return FieldDraft(value=value, sources=data.get("sources", []), needs_check=needs, origin="ai", type=t)


# ---------- 전체/개별 ----------

def draft_one(field: dict, ctx: dict, project: Project, masker: Masker, instruction: str = "",
              docs_text: str | None = None) -> FieldDraft:
    t = field.get("type", "text")
    if field.get("binding") and not instruction:
        fd = data_field(field, ctx)
        if fd is not None:
            if t == "block" and field.get("ai_subfields"):
                ai = ai_field(field, ctx, project, masker, instruction, docs_text, base_items=fd.value)
                ai.sources = fd.sources + ai.sources
                return ai
            return fd
        if t == "image" or not field.get("required", True):
            return FieldDraft(value="", origin="empty", type=t)
    elif field.get("binding") and instruction and t == "block" and field.get("ai_subfields"):
        fd = data_field(field, ctx)
        if fd is not None:
            return ai_field(field, ctx, project, masker, instruction, docs_text, base_items=fd.value)
    if t == "image":
        return FieldDraft(value="", origin="empty", type=t)
    return ai_field(field, ctx, project, masker, instruction, docs_text)


def generate_all(project: Project, force: bool = False,
                 progress: Callable[[int, int, str], None] | None = None) -> dict:
    """GEN-04 전체 초안 생성. 이미 수정/확정된 필드는 건너뛴다(force=False)."""
    schema = templates.load_schema(project.meta["template_id"])
    ctx = context.data_context(project)
    masker = masker_for(project)
    docs_text = context.documents_excerpt(project, masker) if config.has_api_key() else ""
    existing = load_draft(project)["fields"]
    fields = [f for f in schema["fields"]
              if force or existing.get(f["key"], {}).get("status") not in ("edited", "confirmed")]
    if force:
        project.write_json("draft.json", {"fields": {k: v for k, v in existing.items() if v.get("status") in ("edited", "confirmed")}})
    lock = Lock()
    total = len(fields)
    done = 0

    def run(f):
        try:
            return f["key"], draft_one(f, ctx, project, masker, docs_text=docs_text)
        except Exception as e:  # noqa: BLE001  (API 오류: 실패 필드만 표시, 나머지 유지)
            return f["key"], FieldDraft(value="", status="error", error=str(e), type=f.get("type", "text"),
                                        needs_check=[f"생성 실패: {e}"])

    with ThreadPoolExecutor(max_workers=int(config.get("llm.parallel_fields", 3))) as ex:
        futs = [ex.submit(run, f) for f in fields]
        for fut in as_completed(futs):
            key, fd = fut.result()
            save_field(project, key, fd, lock)
            masker.save()
            done += 1
            if progress:
                progress(done, total, key)
    return load_draft(project)


def regenerate(project: Project, key: str, instruction: str = "") -> FieldDraft:
    """GEN-07 필드 재생성(추가 지시 반영)."""
    schema = templates.load_schema(project.meta["template_id"])
    field = next(f for f in schema["fields"] if f["key"] == key)
    ctx = context.data_context(project)
    masker = masker_for(project)
    try:
        fd = draft_one(field, ctx, project, masker, instruction=instruction)
    except Exception as e:  # noqa: BLE001
        fd = FieldDraft(value=load_draft(project)["fields"].get(key, {}).get("value", ""), status="error",
                        error=str(e), type=field.get("type", "text"), needs_check=[f"재생성 실패: {e}"])
    save_field(project, key, fd)
    masker.save()
    return fd


def update_field(project: Project, key: str, value: Any, status: str = "edited") -> None:
    """VAL-01 사용자가 수정/확정."""
    d = load_draft(project)
    cur = d["fields"].get(key, {})
    fd = FieldDraft(**{**cur, "value": value, "status": status, "needs_check": collect_needs_check(value)})
    if cur.get("value") != value:
        fd.origin = "user" if cur.get("origin") != "data" else cur.get("origin")
    save_field(project, key, fd)


def fill_data(project: Project) -> dict:
    """draft.json → hwpx_filler 입력 dict (line_prefix 적용)."""
    schema = templates.load_schema(project.meta["template_id"])
    draft = load_draft(project)["fields"]
    out: dict[str, Any] = {}
    for f in schema["fields"]:
        v = draft.get(f["key"], {}).get("value", "")
        if isinstance(v, str) and f.get("line_prefix"):
            v = "\n".join(f["line_prefix"] + ln for ln in v.split("\n"))
        out[f["key"]] = v
    return out
