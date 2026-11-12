"""HWPX 엔진 테스트 (OUT-01, OUT-02, 절대규칙 3)."""
import zipfile

from fixtures.make_min_hwpx import make

from reportgen.ingest.hwpx import extract
from reportgen.library.templates import extract_fields
from reportgen.render.hwpx_core import HP, HwpxDoc, para_text
from reportgen.render.hwpx_filler import fill


def test_mimetype_first_and_stored(tmp_path):
    src = make(tmp_path / "t.hwpx")
    out = tmp_path / "o.hwpx"
    fill(src, {}, out)
    with zipfile.ZipFile(out) as z:
        first = z.infolist()[0]
        assert first.filename == "mimetype"
        assert first.compress_type == zipfile.ZIP_STORED


def test_split_marker_normalized_and_charpr_kept(tmp_path):
    src = make(tmp_path / "t.hwpx")
    out = tmp_path / "o.hwpx"
    r = fill(src, {"사업명": "테스트사업"}, out)
    doc = HwpxDoc.load(out)
    p0 = doc.sections()[0].findall(f"{HP}p")[0]
    assert para_text(p0) == "제목: 테스트사업 보고"
    run_with = [r_ for r_ in p0.findall(f"{HP}run") if "테스트사업" in "".join(t.text or "" for t in r_.iter(f"{HP}t"))]
    assert run_with[0].get("charPrIDRef") == "5"   # 첫 run 글자모양 유지
    assert "{{사업명}}" not in str(r["remaining"])


def test_paragraph_lines_table_rows_blocks_escape(tmp_path):
    src = make(tmp_path / "t.hwpx")
    out = tmp_path / "o.hwpx"
    data = {
        "사업명": "A", "추진목적": "목적1\n목적2\n목적3",
        "예산": [{"항목": "식대", "금액": "100"}, {"항목": "버스", "금액": "200"}, {"항목": "보험", "금액": "30"}],
        "계획": [{"제목": "T1", "내용": "C1"}, {"제목": "T2", "내용": "C2"}],
        "합계": "330 & <원>",
    }
    r = fill(src, data, out)
    assert r["remaining"] == []
    doc = extract(out)
    text = doc.text()
    assert "목적1" in text and "목적3" in text
    assert "T1" in text and "C2" in text and "{{" not in text
    tbl = [b for b in doc.blocks if b.kind == "table"][0]
    assert tbl.rows == [["항목", "금액"], ["식대", "100"], ["버스", "200"], ["보험", "30"]]
    raw = HwpxDoc.load(out).read("Contents/section0.xml").decode()
    assert "330 &amp; &lt;원&gt;" in raw                      # 값의 XML 이스케이프
    assert 'rowCnt="4"' in raw
    # 문단모양(paraPrIDRef=7) 유지된 채 3개 문단으로 복제
    ps = [p for p in HwpxDoc.load(out).sections()[0].findall(f"{HP}p") if p.get("paraPrIDRef") == "7"]
    assert [para_text(p) for p in ps] == ["목적1", "목적2", "목적3"]


def test_remaining_markers_reported(tmp_path):
    src = make(tmp_path / "t.hwpx")
    r = fill(src, {"사업명": "A"}, tmp_path / "o.hwpx")
    assert "{{합계}}" in r["remaining"]


def test_extract_fields_types(tmp_path):
    src = make(tmp_path / "t.hwpx")
    f = {x["key"]: x for x in extract_fields(src)}
    assert f["예산"]["type"] == "table" and f["예산"]["columns"] == ["항목", "금액"]
    assert f["계획"]["type"] == "block" and f["계획"]["columns"] == ["제목", "내용"]
    assert f["추진목적"]["type"] == "paragraph"
    assert "항목" not in f and "제목" not in f


def test_default_template_fill(template_path, tmp_path):
    from PIL import Image
    img = tmp_path / "a.jpg"
    Image.new("RGB", (800, 600), (10, 20, 30)).save(img)
    out = tmp_path / "o.hwpx"
    keys = [x["key"] for x in extract_fields(template_path)]
    data = {k: f"값_{k}" for k in keys}
    data.update({"운영일정": [{"날짜": "1일", "시간": "10:00", "내용": "개회", "비고": ""}],
                 "만족도문항": [{"문항": "Q1", "응답분포": "x", "차트": str(img), "분석": "A"}],
                 "향후계획": [{"제목": "t", "내용": "c"}], "계획대비실적": [], "예산집행내역": [],
                 "사진1": str(img)})
    for k in [k for k in keys if k.startswith("사진") and k != "사진1"]:
        data.pop(k)
    r = fill(template_path, data, out)
    assert r["remaining"] == []
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
        assert names[0] == "mimetype"
        assert any(n.startswith("BinData/") for n in names)
