"""건별 처리 흐름 (기능정의서 2장 ②). UI와 CLI가 공통으로 사용."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from . import config, ingest, llm
from .analyze import actual as actual_mod
from .analyze import compare
from .analyze import plan as plan_mod
from .generate import drafter
from .library import templates
from .project import Project
from .render import hwpx_filler, pdf
from .validate import checks, report

Progress = Callable[[int, int, str], None] | None


def extract_all(project: Project, progress: Progress = None, force: bool = False) -> list[ingest.ExtractedDoc]:
    """ING-01~06 계획안·자료 전체 추출 → work/extracted"""
    jobs = [(p, "plan") for p in project.files("plan")] + [(p, "material") for p in project.files("materials")]
    out = []
    conv_dir = project.work / "converted"
    for i, (p, role) in enumerate(jobs, 1):
        cached = project.extracted_dir / f"{p.name}.json"
        if cached.exists() and not force and cached.stat().st_mtime >= p.stat().st_mtime:
            doc = ingest.ExtractedDoc.model_validate_json(cached.read_text(encoding="utf-8"))
        else:
            doc = ingest.extract(p, work_dir=conv_dir)
            doc.role = role
            ingest.save_extracted(doc, project.extracted_dir)
        out.append(doc)
        if progress:
            progress(i, len(jobs), p.name)
    # 삭제된 원본의 추출물 정리
    names = {p.name for p, _ in jobs}
    for j in project.extracted_dir.glob("*.json"):
        if j.stem not in names:
            j.unlink()
            j.with_suffix(".md").unlink(missing_ok=True)
    return out


def structure(project: Project) -> dict:
    """GEN-01~03 plan.json / actual.json / comparison.json"""
    docs = ingest.load_extracted(project.extracted_dir)
    plans = [d for d in docs if d.role == "plan"]
    mats = [d for d in docs if d.role != "plan" and d.type != "image"]
    masker = drafter.masker_for(project)
    plan, u1 = plan_mod.build(plans, masker, project.logs_dir, project.meta.get("name", ""))
    project.write_json("plan.json", plan)
    actual, u2 = actual_mod.build(mats, plan, masker, project.logs_dir)
    project.write_json("actual.json", actual)
    cmp_ = compare.build(plan, actual)
    project.write_json("comparison.json", cmp_)
    masker.save()
    # 차트는 수치가 바뀌었을 수 있으므로 다시 그림
    for c in (project.work / "charts").glob("*.png"):
        c.unlink()
    return {"plan": plan, "actual": actual, "comparison": cmp_, "usage": [u1, u2]}


def estimate(project: Project) -> dict:
    """NFR-11 생성 전 예상 토큰·비용"""
    docs = ingest.load_extracted(project.extracted_dir)
    chars = sum(len(d.text()) for d in docs)
    schema = templates.load_schema(project.meta["template_id"])
    n_ai = sum(1 for f in schema["fields"] if not f.get("binding") or f.get("ai_subfields"))
    excerpt = min(chars, int(config.get("ingest.max_excerpt_chars", 60000)))
    return llm.estimate_cost(input_chars=chars * 2 + n_ai * (excerpt + 9000), n_calls=n_ai + 2) | {"ai_fields": n_ai}


def render_output(project: Project, make_pdf: bool = True) -> dict:
    """OUT-01~06 hwpx(+pdf) 생성, 검증, 근거보고서"""
    tid = project.meta["template_id"]
    data = drafter.fill_data(project)
    base = project.output_basename()
    out_hwpx = project.output_dir / f"{base}.hwpx"
    res = hwpx_filler.fill(templates.template_path(tid), data, out_hwpx)
    val = checks.run(project, rendered_remaining=res["remaining"])
    rep = report.write(project, val)
    out = {"hwpx": str(out_hwpx), "report": str(rep), "validation": val, "fill": dict(res), "pdf": None}
    if make_pdf:
        out["pdf"] = pdf.to_pdf(out_hwpx, project.output_dir / f"{base}.pdf")
    return out


def run_all(project: Project, progress: Progress = None, make_pdf: bool = True) -> dict:
    extract_all(project)
    structure(project)
    drafter.generate_all(project, progress=progress)
    return render_output(project, make_pdf)


def open_folder(path: str | Path) -> None:
    import os
    import sys
    if sys.platform == "win32":
        os.startfile(str(path))  # noqa: S606
