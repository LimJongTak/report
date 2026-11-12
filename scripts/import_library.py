"""라이브러리 일괄 등록 CLI (LIB-10 / F-05).

python scripts/import_library.py --templates <양식폴더> --examples <과거보고폴더> [--plans <계획안폴더>]
python scripts/import_library.py --build-default <과거보고.hwp|hwpx>   # 과거 보고서로 기본 양식 생성·등록

- 양식: .hwpx(마킹된 것). .hwp는 한컴으로 .hwpx 변환 후 등록
- 과거 보고서: .hwp/.hwpx/.pdf/.docx. 같은 이름의 hwp와 pdf가 있으면 hwp를 우선
- 계획안: 파일명이 가장 비슷한 과거 보고서에 plan.md로 연결(백테스트용)
"""
from __future__ import annotations

import argparse
import difflib
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

import yaml  # noqa: E402

from reportgen import config, hancom  # noqa: E402
from reportgen.library import examples, style, templates  # noqa: E402

DEFAULT_ID = "aiboot_result_v1"
DEFAULT_NAME = "AIBOOT 결과보고 표준양식 (행사·견학·특강형)"


def hints_for(template_id: str) -> dict:
    p = ROOT / "config" / "template_hints" / f"{template_id}.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else {}


def _as_hwpx(path: Path, tmp: Path) -> Path:
    if path.suffix.lower() == ".hwpx":
        return path
    dst = tmp / (path.stem + ".hwpx")
    r = hancom.hwp_to_hwpx(path, dst)
    if not r.get("ok"):
        raise SystemExit(f"{path.name}: 한컴 변환 실패({r.get('error')}). 한컴에서 .hwpx로 저장해 다시 실행하세요.")
    return dst


def build_default(src: Path) -> dict:
    tmp = Path(tempfile.mkdtemp())
    hwpx = _as_hwpx(src, tmp)
    out = tmp / "template.hwpx"
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_default_template
    build_default_template.main(str(hwpx), str(out))
    schema = templates.register(out, DEFAULT_ID, DEFAULT_NAME, hints=hints_for(DEFAULT_ID), original=src)
    return schema


def import_templates(folder: Path) -> list[dict]:
    tmp = Path(tempfile.mkdtemp())
    out = []
    for p in sorted(folder.glob("*")):
        if p.suffix.lower() not in (".hwpx", ".hwp"):
            continue
        tid = re.sub(r"[^0-9A-Za-z가-힣_]+", "_", p.stem).strip("_")[:40]
        hwpx = _as_hwpx(p, tmp)
        s = templates.register(hwpx, tid, p.stem, hints=hints_for(tid), original=p)
        out.append({"양식": p.name, "ID": tid, "필드 수": len(s["fields"])})
    return out


def import_examples(folder: Path, plans: Path | None, template_id: str | None) -> list[dict]:
    files = [p for p in sorted(folder.glob("*")) if p.suffix.lower() in (".hwp", ".hwpx", ".pdf", ".docx")]
    by_stem: dict[str, list[Path]] = {}
    for p in files:
        by_stem.setdefault(p.stem, []).append(p)
    pick = []
    for stem, ps in by_stem.items():
        ps.sort(key=lambda x: [".hwpx", ".hwp", ".docx", ".pdf"].index(x.suffix.lower()))
        pick.append(ps[0])
    plan_files = [p for p in sorted(plans.glob("*")) if p.is_file()] if plans else []
    tmp = Path(tempfile.mkdtemp())
    rows = []
    for p in pick:
        plan = None
        if plan_files:
            key = re.sub(r"결과\s*보고(서)?|계획(안)?|\(.*?\)|붙임\s*\d+\.", "", p.stem)
            scored = [(difflib.SequenceMatcher(None, key, re.sub(r"결과\s*보고(서)?|계획(안)?|\(.*?\)|붙임\s*\d+\.", "", q.stem)).ratio(), q) for q in plan_files]
            best = max(scored, key=lambda x: x[0])
            if best[0] >= 0.5:
                plan = best[1]
        m = examples.register(p, template_id, plan=plan, work_dir=tmp)
        rows.append({"파일": p.name, "사업유형": m["사업유형"], "추출": m["추출경로"], "상태": m["추출상태"],
                     "계획안": m.get("계획안", "-")})
    return rows


def table(rows: list[dict]) -> str:
    if not rows:
        return "(없음)"
    cols = list(rows[0].keys())
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(str(r.get(c, "")) for c in cols) + " |" for r in rows]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="ReportGen 라이브러리 일괄 등록")
    ap.add_argument("--templates", type=Path)
    ap.add_argument("--examples", type=Path)
    ap.add_argument("--plans", type=Path)
    ap.add_argument("--build-default", type=Path, help="과거 결과보고서로 기본 양식 생성")
    ap.add_argument("--no-style", action="store_true", help="문체 프로필 갱신 생략")
    a = ap.parse_args()
    if a.build_default:
        s = build_default(a.build_default)
        print(f"\n## 기본 양식 등록: {DEFAULT_ID} (필드 {len(s['fields'])}개)")
    if a.templates:
        print("\n## 양식 등록\n" + table(import_templates(a.templates)))
    if a.examples:
        tid = DEFAULT_ID if (templates.templates_dir() / DEFAULT_ID).exists() else None
        print("\n## 과거 결과보고 등록\n" + table(import_examples(a.examples, a.plans, tid)))
    if (a.examples or a.build_default) and not a.no_style:
        p = style.build(use_ai=True, log_dir=config.path("library") / "logs")
        print(f"\n## 문체 프로필 생성: {p} ({'Claude 분석' if config.has_api_key() else 'API 키 없음 → 코드 통계 + 기본 프로필'})")


if __name__ == "__main__":
    main()
