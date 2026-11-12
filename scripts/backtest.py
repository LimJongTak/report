"""백테스트: 과거 사례를 가린 채 계획안(+자료)만으로 다시 생성해 실제 보고서와 비교 (P9).

python scripts/backtest.py [--example <사례ID>] [--materials <결과자료 폴더>]

비교 항목(필드별): 실제 보고서 수치 중 생성본에 없는 것(누락 수치), 생성본에만 있는 수치(근거 없는 수치 후보),
[확인 필요] 개수, 문장 끝 유형(개조식/서술형) 차이. 결과: docs/백테스트결과.md
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

import yaml  # noqa: E402

from reportgen import config, pipeline, project  # noqa: E402
from reportgen.generate import drafter  # noqa: E402
from reportgen.library import examples  # noqa: E402
from reportgen.validate import checks  # noqa: E402

NUM = re.compile(r"\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?")


def numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in NUM.findall(text) if len(n.replace(",", "")) >= 2}


def endings(text: str) -> dict:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return {"서술형": sum(bool(re.search(r"습니다\.?$", ln)) for ln in lines),
            "개조식": sum(bool(re.search(r"(함|임|됨|제고|강화|확대|구축|향상|확보|마련|필요)$", ln)) for ln in lines)}


def run_one(ex: dict, materials: Path | None) -> dict:
    d = Path(ex["dir"])
    plan_src = next(d.glob("plan_source.*"), None)
    p = project.create(f"[백테스트] {ex['사업명']}", ex.get("양식ID") or "aiboot_result_v1", ex.get("일자") or dt.date.today().isoformat())
    if plan_src:
        p.add_file(plan_src, "계획안" + plan_src.suffix, "plan")
    if materials and materials.exists():
        for f in materials.glob("*"):
            if f.is_file():
                p.add_file(f, f.name, "materials")
    pipeline.extract_all(p)
    pipeline.structure(p)
    drafter.generate_all(p)
    val = checks.run(p)
    gen = drafter.load_draft(p)["fields"]
    gen_text = "\n".join(checks._flatten(v.get("value")) for v in gen.values())
    real = examples.load_text(ex["id"])
    rn, gn = numbers(real), numbers(gen_text)
    out = {
        "사례": ex["사업명"], "프로젝트": p.id,
        "누락 수치(실제에만)": sorted(rn - gn)[:30],
        "생성본에만 있는 수치": sorted(gn - rn)[:30],
        "확인 필요": val["summary"]["needs_check"],
        "근거 없는 숫자": val["summary"]["unsupported_numbers"],
        "문체(실제)": endings(real), "문체(생성)": endings(gen_text),
        "계획안": bool(plan_src),
    }
    pipeline.render_output(p, make_pdf=False)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--example")
    ap.add_argument("--materials", type=Path)
    a = ap.parse_args()
    exs = [e for e in examples.list_examples() if e.get("추출상태") == "정상"]
    if a.example:
        exs = [e for e in exs if e["id"] == a.example]
    with_plan = [e for e in exs if e.get("계획안")]
    if not with_plan:
        print("계획안(plan.md)이 연결된 사례가 없습니다. import_library.py --plans <계획안폴더>로 계획안을 연결하세요.")
        if not exs:
            return
        print("계획안 없이 사례 이름만으로 생성해 문체·구성만 비교합니다.")
        with_plan = exs[:2]
    results = [run_one(e, a.materials) for e in with_plan]
    lines = [f"# 백테스트 결과 ({dt.datetime.now():%Y-%m-%d %H:%M})", "",
             f"- 모델: {config.get('llm.model')} / AI 연결: {'예' if config.has_api_key() else '아니오(코드 계산 항목만)'}", ""]
    for r in results:
        lines += [f"## {r['사례']}", "", f"- 생성 프로젝트: `projects/{r['프로젝트']}`", f"- 계획안 사용: {r['계획안']}",
                  f"- [확인 필요] {r['확인 필요']}개, 근거 없는 숫자 {r['근거 없는 숫자']}개",
                  f"- 누락 수치(실제 보고서에만 있음): {', '.join(r['누락 수치(실제에만)']) or '없음'}",
                  f"- 생성본에만 있는 수치: {', '.join(r['생성본에만 있는 수치']) or '없음'}",
                  f"- 문장 끝 유형 실제 {r['문체(실제)']} / 생성 {r['문체(생성)']}", ""]
    out = ROOT / "docs" / "백테스트결과.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("저장:", out)


if __name__ == "__main__":
    main()
