"""근거보고서.md 생성 (VAL-05)."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from ..generate.drafter import load_draft
from ..library import templates
from ..project import Project

ORIGIN = {"data": "자료·코드 계산", "ai": "AI 초안", "user": "사용자 작성", "empty": "비어 있음"}
STATUS = {"draft": "초안", "edited": "수정됨", "confirmed": "확정", "error": "오류"}


def _value_md(v) -> str:
    if isinstance(v, list):
        if v and isinstance(v[0], dict):
            cols = [c for c in v[0].keys() if c != "차트"]
            lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
            lines += ["| " + " | ".join(str(r.get(c, "")).replace("\n", " ").replace("|", "/") for c in cols) + " |" for r in v]
            return "\n".join(lines)
        return "\n".join(f"- {x}" for x in v)
    if isinstance(v, str) and v.lower().endswith((".jpg", ".jpeg", ".png")):
        return f"(이미지) {Path(v).name}"
    return "\n".join(f"> {ln}" for ln in str(v or "(비어 있음)").split("\n"))


def write(project: Project, validation: dict, out_path: Path | None = None) -> Path:
    schema = templates.load_schema(project.meta["template_id"])
    fields = load_draft(project)["fields"]
    s = validation["summary"]
    lines = [
        f"# 근거보고서 — {project.meta.get('name')}",
        "",
        f"- 생성: {dt.datetime.now():%Y-%m-%d %H:%M} / 양식: {schema.get('name')} ({schema.get('template_id')})",
        f"- 검증 요약: 오류 {s['errors']}건, 경고 {s['warnings']}건, [확인 필요] {s['needs_check']}개, "
        f"근거 없는 숫자 {s['unsupported_numbers']}개, 빈 필수 필드 {s['empty_required']}개",
        "",
        "## 1. 검증 결과",
        "",
    ]
    if validation["issues"]:
        lines += ["| 수준 | 필드 | 유형 | 내용 |", "|---|---|---|---|"]
        icon = {"error": "오류", "warn": "경고", "info": "참고"}
        lines += [f"| {icon[i['level']]} | {i['field']} | {i['kind']} | {i['detail']} |" for i in validation["issues"]]
    else:
        lines.append("문제 없음.")
    lines += ["", "## 2. 필드별 내용과 근거", ""]
    for f in schema["fields"]:
        fd = fields.get(f["key"], {})
        fv = validation["fields"].get(f["key"], {})
        lines.append(f"### {f['key']}  `{f.get('type', 'text')}` · {ORIGIN.get(fd.get('origin'), '-')} · {STATUS.get(fd.get('status'), '-')}")
        lines.append("")
        lines.append(_value_md(fd.get("value")))
        lines.append("")
        srcs = fd.get("sources") or []
        if srcs:
            lines.append("근거:")
            for sr in srcs:
                q = f' — "{sr.get("quote")}"' if sr.get("quote") else ""
                lines.append(f"- {sr.get('file', '')} {sr.get('loc', '')}{q}")
        else:
            lines.append("근거: (기록 없음)")
        if fv.get("unsupported_numbers"):
            lines.append(f"- ⚠ 근거 없는 숫자: {', '.join(fv['unsupported_numbers'])}")
        for r in fv.get("needs_check", []):
            lines.append(f"- ⚠ 확인 필요: {r}")
        lines.append("")
    out = out_path or project.output_dir / "근거보고서.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    return out
