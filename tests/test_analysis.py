"""추출·구조화·계산·검증 테스트 (ING, GEN-03, GEN-09, VAL, NFR-02)."""
import sample_data

from reportgen import ingest, pipeline, project
from reportgen.analyze import compare, sheets
from reportgen.generate import drafter
from reportgen.generate.formatting import fmt_date, fmt_date_range, fmt_money, fmt_pct, ratio
from reportgen.privacy import Masker
from reportgen.validate import checks


def test_formatting():
    assert fmt_date("2026-07-10") == "2026. 07. 10.(금)"
    assert fmt_date_range("2026-10-22", "2026-10-23") == "2026. 10. 22.(목) ~ 10. 23.(금)"
    assert fmt_money(1281640) == "1,281,640"
    assert fmt_pct(ratio(32, 30)) == "106.7%"
    assert ratio(5, 0) is None


def test_masking_roundtrip(tmp_path):
    m = Masker(tmp_path / "t.json")
    m.learn_names_from_rows([["성명", "연락처"], ["김하늘", "010-1234-5678"]])
    s = m.mask("김하늘 학생(010-1234-5678, sky@test.kr)")
    assert "김하늘" not in s and "010" not in s and "sky@" not in s
    assert m.unmask(s) == "김하늘 학생(010-1234-5678, sky@test.kr)"


def test_ingest_and_code_facts(tmp_path):
    src = sample_data.make(tmp_path / "in")
    docs = [ingest.extract(f) for f in sorted(src["materials"].glob("*"))]
    s = sheets.detect_survey(docs)
    assert s and s["응답자수"] == 20 and len(s["items"]) == 4
    assert all(sum(i["응답"].values()) == 20 for i in s["items"])
    r = sheets.detect_roster(docs)
    assert r["명단인원"] == 23 and r["참석인원"] == 22
    b = sheets.detect_budget(docs)
    assert b["합계"] == 1210000 and b["합계일치"]
    img = [d for d in docs if d.type == "image"]
    assert img and img[0].meta["photo_candidate"]


def test_compare_is_code_calculated():
    plan = {"목표인원": 30, "예산": [{"금액": 1000000}, {"금액": 500000}]}
    actual = {"참여인원": 32, "집행내역": [{"금액": 1200000}, {"금액": 150000}]}
    rows = {r["항목"]: r for r in compare.build(plan, actual)["rows"]}
    assert rows["참여인원"]["달성률"] == "106.7%"
    assert rows["예산 집행"]["달성률"] == "90.0%"
    assert rows["예산 집행"]["실적"] == "1,350,000원"


def _offline_project(tmp_path, template_id="aiboot_result_v1"):
    src = sample_data.make(tmp_path / "in")
    p = project.create("2026 클라우드 기업 현장견학", template_id, "2026-11-05")
    for f in src["plan"].glob("*"):
        p.add_file(f, f.name, "plan")
    for f in src["materials"].glob("*"):
        p.add_file(f, f.name, "materials")
    pipeline.extract_all(p)
    pipeline.structure(p)
    drafter.generate_all(p)
    return p


def test_offline_pipeline_end_to_end(isolated, template_path):
    p = _offline_project(isolated)
    d = drafter.load_draft(p)["fields"]
    assert d["참여인원"]["value"] == "22명"
    assert d["예산합계"]["value"] == "1,210,000"
    rows = {r["항목"]: r for r in d["계획대비실적"]["value"]}
    assert rows["참여인원"]["달성률"] == "88.0%"
    assert d["행사일시"]["value"] == "" or "2026" in str(d["행사일시"]["value"]) or d["행사일시"]["origin"] == "empty"
    assert "AI 미연결" in d["추진배경"]["value"]                 # 지어내지 않고 [확인 필요]
    assert len(d["만족도문항"]["value"]) == 4
    out = pipeline.render_output(p, make_pdf=False)
    assert out["fill"]["remaining"] == []
    assert (p.output_dir / "근거보고서.md").exists()
    assert p.output_basename().startswith("20261105_")


def test_validation_flags_wrong_number(isolated, template_path):
    p = _offline_project(isolated)
    drafter.update_field(p, "운영결과", "총 57명이 참여하여 성황리에 마쳤습니다.")
    drafter.update_field(p, "예산합계", "9,999,999")
    v = checks.run(p)
    kinds = {(i["field"], i["kind"]) for i in v["issues"]}
    assert ("운영결과", "근거 없는 숫자") in kinds
    assert ("예산합계", "합계 불일치") in kinds
    assert v["summary"]["needs_check"] > 0
