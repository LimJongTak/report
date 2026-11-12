"""기본 결과보고 양식(aiboot_result_v1) 생성 스크립트.

과거 결과보고서(네이버클라우드 사옥투어, 한컴에서 HWPX로 저장한 것)를 바탕으로
서식(글꼴·표·여백)은 그대로 두고 내용만 {{필드}} 마커로 바꾼 양식을 만든다.

사용: python scripts/build_default_template.py <원본.hwpx> <출력_양식.hwpx>
"""
from __future__ import annotations

import copy
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image, ImageDraw  # noqa: E402

from reportgen.render.hwpx_core import HC, HH, HP, HwpxDoc, para_text, set_para_text  # noqa: E402


def placeholder(w=764, h=434, label="IMAGE") -> bytes:
    im = Image.new("RGB", (w, h), (235, 235, 235))
    d = ImageDraw.Draw(im)
    d.rectangle([2, 2, w - 3, h - 3], outline=(180, 180, 180), width=3)
    d.text((w // 2 - 20, h // 2 - 6), label, fill=(150, 150, 150))
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


def expect(p, text_start: str):
    t = para_text(p).strip()
    if not t.startswith(text_start):
        raise SystemExit(f"예상과 다른 원본 구조: '{text_start}' 기대, 실제 '{t[:30]}'")


def cell_paras(tbl, r, c):
    for tr in tbl.findall(f"{HP}tr"):
        for tc in tr.findall(f"{HP}tc"):
            a = tc.find(f"{HP}cellAddr")
            if a.get("rowAddr") == str(r) and a.get("colAddr") == str(c):
                return tc, tc.find(f"{HP}subList").findall(f"{HP}p")
    raise KeyError((r, c))


def set_cell(tbl, r, c, text):
    tc, ps = cell_paras(tbl, r, c)
    set_para_text(ps[0], text)
    for p in ps[1:]:
        p.getparent().remove(p)
    return tc


def make_repeat_row(tbl, header_rows: int, src_row_idx: int, texts: list[str], keep_after: int = 0):
    """header 다음에 반복 마커 행 하나만 남긴다. keep_after: 끝에서 유지할 행 수(합계 등)."""
    trs = tbl.findall(f"{HP}tr")
    src = trs[src_row_idx]
    row = copy.deepcopy(src)
    tcs = row.findall(f"{HP}tc")
    # 열 정렬: colAddr 순으로 텍스트 배치, rowSpan=1, 높이는 일반 행 높이
    h = min(int(tc.find(f"{HP}cellSz").get("height")) for tr in trs[header_rows:] for tc in tr.findall(f"{HP}tc"))
    for tc in tcs:
        tc.find(f"{HP}cellSpan").set("rowSpan", "1")
        tc.find(f"{HP}cellSz").set("height", str(h))
    if len(tcs) != int(tbl.get("colCnt")):
        raise SystemExit("반복 행 원본은 모든 열을 가진 행이어야 합니다")
    tcs = sorted(row.findall(f"{HP}tc"), key=lambda tc: int(tc.find(f"{HP}cellAddr").get("colAddr")))
    for tc in row.findall(f"{HP}tc"):
        row.remove(tc)
    for tc, text in zip(tcs, texts):
        ps = tc.find(f"{HP}subList").findall(f"{HP}p")
        set_para_text(ps[0], text)
        for p in ps[1:]:
            p.getparent().remove(p)
        row.append(tc)
    # 기존 데이터 행 제거 후 삽입
    tail = trs[len(trs) - keep_after:] if keep_after else []
    for tr in trs[header_rows:]:
        if tr not in tail:
            tbl.remove(tr)
    tbl.insert(tbl.index(trs[header_rows - 1]) + 1, row)
    for r, tr in enumerate(tbl.findall(f"{HP}tr")):
        for tc in tr.findall(f"{HP}tc"):
            tc.find(f"{HP}cellAddr").set("rowAddr", str(r))
    tbl.set("rowCnt", str(len(tbl.findall(f"{HP}tr"))))
    tot = sum(max(int(tc.find(f"{HP}cellSz").get("height")) for tc in tr.findall(f"{HP}tc")) for tr in tbl.findall(f"{HP}tr"))
    tbl.find(f"{HP}sz").set("height", str(tot))


def set_col_widths(tbl, widths: list[int]) -> None:
    """열 너비 지정(병합 셀은 합산)."""
    for tc in tbl.iter(f"{HP}tc"):
        c = int(tc.find(f"{HP}cellAddr").get("colAddr"))
        span = int(tc.find(f"{HP}cellSpan").get("colSpan"))
        tc.find(f"{HP}cellSz").set("width", str(sum(widths[c:c + span])))
        for p in tc.iter(f"{HP}p"):
            for ls in p.findall(f"{HP}linesegarray"):
                p.remove(ls)
    tbl.find(f"{HP}sz").set("width", str(sum(widths)))


def main(src: str, out: str):
    doc = HwpxDoc.load(src)
    sec = doc.xml("Contents/section0.xml")
    P = sec.findall(f"{HP}p")
    tbl_of = lambda p: next(p.iter(f"{HP}tbl"))  # noqa: E731
    remove = set()

    # ── 제목 상자 ──
    title = tbl_of(P[0])
    _, tps = cell_paras(title, 1, 0)
    runs = tps[0].findall(f"{HP}run")
    runs[0].find(f"{HP}t").text = "「"
    runs[1].find(f"{HP}t").text = "{{사업단명}}"
    runs[2].find(f"{HP}t").text = "」"
    for r in runs[3:]:
        tps[0].remove(r)
    set_para_text(tps[1], "{{보고서제목}}")
    tps[2].getparent().remove(tps[2])
    for p in (tps[0],):
        for ls in p.findall(f"{HP}linesegarray"):
            p.remove(ls)

    # ── Ⅰ 사업개요 ──
    expect(P[2], "추진배경")
    set_para_text(P[3], "{{추진배경}}"); remove |= {4, 5}
    P[3].set("paraPrIDRef", P[8].get("paraPrIDRef"))  # 추진목적과 같은 '-' 자동 글머리
    expect(P[7], "추진목적")
    set_para_text(P[8], "{{추진목적}}"); remove |= {9, 10}
    expect(P[12], "행사 개요")
    set_para_text(P[13], "행 사 명 : {{행사명}}")
    set_para_text(P[14], "행사일시 : {{행사일시}}")
    set_para_text(P[15], "장    소 : {{장소}}")
    set_para_text(P[16], "대    상 : {{대상}}")
    extra = copy.deepcopy(P[16])
    set_para_text(extra, "참여인원 : {{참여인원}}")
    sec.insert(sec.index(P[16]) + 1, extra)

    # ── 2 주요 추진내용 ──
    expect(P[19], "주요 추진내용")
    set_para_text(P[20], "{{주요추진내용}}"); remove |= {21}
    P[20].set("paraPrIDRef", P[8].get("paraPrIDRef"))
    expect(P[23], "운영일정")
    make_repeat_row(tbl_of(P[24]), 1, 1, ["{{#운영일정}}{{날짜}}", "{{시간}}", "{{내용}}", "{{비고}}"])
    set_col_widths(tbl_of(P[24]), [8457, 10000, 18500, 11000])

    # ── 3 운영 성과 ──
    expect(P[28], "현장 중심")
    set_para_text(P[28], "{{성과제목}}")
    set_para_text(P[29], "{{운영결과}}")
    # 계획 대비 실적: 소제목 + 표(운영일정 표 복제)
    h = copy.deepcopy(P[34]); set_para_text(h, "계획 대비 실적")
    t = copy.deepcopy(P[24])
    sec.insert(sec.index(P[30]) + 1, h)
    sec.insert(sec.index(h) + 1, t)
    ct = tbl_of(t)
    for c, txt in enumerate(["항목", "계획", "실적", "달성률"]):
        set_cell(ct, 0, c, txt)
    set_cell(ct, 1, 0, "{{#계획대비실적}}{{항목}}"); set_cell(ct, 1, 1, "{{계획}}")
    set_cell(ct, 1, 2, "{{실적}}"); set_cell(ct, 1, 3, "{{달성률}}")
    set_col_widths(ct, [15957, 12000, 12000, 8000])
    sp = copy.deepcopy(P[30]); sec.insert(sec.index(t) + 1, sp)

    expect(P[31], "현장견학 만족도")
    set_para_text(P[31], "만족도 조사 결과")
    set_para_text(P[32], "{{만족도요약}}")
    set_para_text(P[34], "만족도 조사 현황")
    st = tbl_of(P[35])
    for r, k in enumerate(["조사기간", "조사대상", "응답자수", "조사방법", "활용목적"], start=1):
        set_cell(st, r, 1, "{{%s}}" % k)
    # 문항 블록 (제목, 응답분포, 차트, 분석) 1세트만 남김
    set_para_text(P[37], "{{#만족도문항}}{{문항}} (설문:응답자수)")
    set_para_text(P[38], "{{응답분포}}")
    pic = next(P[39].iter(f"{HP}pic"))
    pic.find(f"{HP}shapeComment").text = "{{차트}}"
    set_para_text(P[40], "{{분석}}{{/만족도문항}}")
    remove |= set(range(41, 73))
    expect(P[73], "주요 성과")
    set_para_text(P[74], "{{주요성과}}"); remove |= {75, 76, 77}

    # ── 4 향후 활용계획 ──
    set_cell(tbl_of(P[79]), 0, 1, " 향후 활용계획")
    set_para_text(P[81], "{{#향후계획}}{{제목}}")
    set_para_text(P[82], "{{내용}}{{/향후계획}}")
    remove |= {83, 84, 85, 86}

    # ── 5 소요예산 ──
    set_para_text(P[90], " ◦ 재원 – {{재원}} : 금 {{예산총액}}원")
    bt = tbl_of(P[92])
    make_repeat_row(bt, 1, 1, ["{{#예산집행내역}}{{예산과목}}", "{{세부항목}}", "{{산출내역}}", "{{금액}}"], keep_after=1)
    last = bt.findall(f"{HP}tr")[-1]
    tcs = last.findall(f"{HP}tc")
    set_para_text(tcs[-1].find(f"{HP}subList").findall(f"{HP}p")[0], "{{예산합계}}")

    # ── 6 행사 사진 ──
    pt = tbl_of(P[96])
    n = 1
    for r in range(4):
        for c in range(2):
            set_cell(pt, r, c, "{{사진%d}}" % n)
            n += 1

    for i in sorted(remove, reverse=True):
        sec.remove(P[i])

    # 원본 사진·차트를 자리표시 이미지로 교체 (용량 축소, 개인 사진 제거)
    items = doc.bindata_items()
    for item_id, href in items.items():
        if href and href.startswith("BinData/"):
            doc.replace_bindata(item_id, placeholder(label="PHOTO" if href.endswith(".jpg") else "CHART"), "png")
    doc.write_entry("Preview/PrvText.txt", "결과보고 양식(aiboot_result_v1)".encode("utf-8"))
    doc.write_entry("Preview/PrvImage.png", placeholder(200, 283, "TEMPLATE"))
    from reportgen.render.hwpx_filler import _prune_unused_bindata
    _prune_unused_bindata(doc)
    doc.save(out)
    print("양식 생성:", out)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
