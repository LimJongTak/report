"""S4 출력: 검증 요약, 사진 선택, HWPX/PDF 생성, 폴더 열기."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from .. import pipeline
from ..generate import context, drafter
from ..render import pdf as pdf_mod
from ..validate import checks
from . import common


def render():
    st.title("📄 출력")
    p = common.need_project()
    if not p:
        return
    if not drafter.load_draft(p)["fields"]:
        st.info("초안이 없습니다. '2. 새 결과보고'에서 초안을 먼저 만드세요.")
        return
    val = checks.run(p)
    s = val["summary"]
    if s["errors"] or s["needs_check"] or s["unsupported_numbers"]:
        st.warning(f"오류 {s['errors']} · [확인 필요] {s['needs_check']} · 근거 없는 숫자 {s['unsupported_numbers']} — "
                   "출력은 가능하지만 제출 전에 '3. 검토'에서 정리하세요.")
    else:
        st.success("검증 경고 없음")

    st.subheader("행사 사진 (최대 8장, 선택 순서대로 배치)")
    photos = p.photos()
    if photos:
        default = [Path(x).name for x in context.selected_photos(p)]
        sel = st.multiselect("사진", [f.name for f in photos], default=default, max_selections=8)
        cols = st.columns(4)
        for i, n in enumerate(sel):
            cols[i % 4].image(str(p.materials_dir / n), caption=f"{i + 1}. {n}", width="stretch")
        if sel != p.meta.get("photos"):
            p.update_meta(photos=sel)
            for i in range(8):
                k = f"사진{i + 1}"
                drafter.update_field(p, k, str(p.materials_dir / sel[i]) if i < len(sel) else "", "confirmed")
    else:
        st.caption("올린 사진이 없습니다.")

    st.subheader("파일 만들기")
    st.text_input("출력 파일명", value=p.output_basename() + ".hwpx", disabled=True)
    make_pdf = st.checkbox("PDF도 만들기 (한컴오피스 → LibreOffice 순)", value=True)
    if st.button("📄 HWPX 생성", type="primary"):
        with st.spinner("양식에 채우는 중..." + (" (한컴 보안 창이 뜨면 [접근 허용]을 눌러 주세요)" if make_pdf else "")):
            out = pipeline.render_output(p, make_pdf=make_pdf)
        st.session_state["last_out"] = out
    out = st.session_state.get("last_out")
    if out:
        st.success(f"HWPX: {out['hwpx']}")
        if out["fill"]["remaining"]:
            st.error(f"채워지지 않은 필드: {', '.join(out['fill']['remaining'])}")
        if out.get("pdf"):
            if out["pdf"]["ok"]:
                st.success(f"PDF({out['pdf']['converter']}): {out['pdf']['path']}")
            else:
                st.warning(out["pdf"]["message"])
        st.info(f"근거보고서: {out['report']}")
        c1, c2, c3 = st.columns(3)
        c1.download_button("HWPX 내려받기", Path(out["hwpx"]).read_bytes(), file_name=Path(out["hwpx"]).name)
        if out.get("pdf") and out["pdf"]["ok"]:
            c2.download_button("PDF 내려받기", Path(out["pdf"]["path"]).read_bytes(), file_name=Path(out["pdf"]["path"]).name)
        c3.download_button("근거보고서 내려받기", Path(out["report"]).read_bytes(), file_name="근거보고서.md")
    if st.button("📂 출력 폴더 열기"):
        pipeline.open_folder(p.output_dir)

    with st.expander("PDF 변환기 진단"):
        if st.button("진단 실행"):
            d = pdf_mod.diagnose()
            st.dataframe(pd.DataFrame([{"변환기": k, "사용 가능": v["ok"], "정보": v["detail"]} for k, v in d.items()]),
                         hide_index=True)
