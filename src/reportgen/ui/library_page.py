"""S1 라이브러리 화면: 양식·과거 사례·문체 프로필 관리."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from .. import config
from ..library import examples, style, templates


def render():
    st.title("📚 라이브러리")
    st.caption("결과보고 양식(.hwpx)과 과거 결과보고서를 등록해 두면, 새 보고서를 같은 양식·문체로 만듭니다.")
    t1, t2, t3 = st.tabs(["양식", "과거 결과보고", "문체 프로필"])

    with t1:
        tl = templates.list_templates()
        if tl:
            st.dataframe(pd.DataFrame(tl)[["id", "name", "fields"]].rename(columns={"id": "양식ID", "name": "이름", "fields": "필드 수"}),
                         hide_index=True, width="stretch")
        sel = st.selectbox("양식 선택", [t["id"] for t in tl], key="lib_tpl") if tl else None
        if sel:
            schema = templates.load_schema(sel)
            st.markdown("**필드 정의(schema.yaml)** — 표에서 직접 고친 뒤 [저장]")
            cols = ["key", "type", "required", "binding", "guide", "max_chars", "line_prefix"]
            df = pd.DataFrame([{c: f.get(c) for c in cols} for f in schema["fields"]])
            edited = st.data_editor(df, hide_index=True, width="stretch", disabled=["key"], key=f"ed_{sel}",
                                    column_config={"type": st.column_config.SelectboxColumn(
                                        options=["text", "paragraph", "table", "block", "image", "date", "number"])})
            c1, c2 = st.columns([1, 5])
            if c1.button("저장", key="save_schema"):
                rows = {r["key"]: r for r in edited.to_dict("records")}
                for f in schema["fields"]:
                    for c in cols[1:]:
                        v = rows[f["key"]].get(c)
                        if v is None or (isinstance(v, float) and pd.isna(v)) or v == "":
                            f.pop(c, None)
                        else:
                            f[c] = int(v) if c == "max_chars" else v
                templates.save_schema(sel, schema)
                st.success("저장했습니다.")
            if c2.button("이 양식 삭제", key="del_tpl"):
                templates.delete(sel)
                st.rerun()
        st.divider()
        st.markdown("**새 양식 등록** — 한글에서 채울 칸에 `{{사업명}}`처럼 적고, 반복 행은 첫 칸에 `{{#표이름}}`을 적어 .hwpx로 저장하세요.")
        up = st.file_uploader("양식(.hwpx)", type=["hwpx"], key="tpl_up")
        tid = st.text_input("양식ID (영문/숫자/밑줄)", key="tpl_id")
        tname = st.text_input("양식 이름", key="tpl_name")
        if st.button("양식 등록", disabled=not (up and tid)):
            tmp = Path(tempfile.mkdtemp()) / up.name
            tmp.write_bytes(up.getvalue())
            s = templates.register(tmp, tid, tname or tid)
            st.success(f"등록 완료: 필드 {len(s['fields'])}개")
            st.rerun()

    with t2:
        ex = examples.list_examples()
        if ex:
            df = pd.DataFrame(ex)
            show = [c for c in ["id", "사업유형", "연도", "추출경로", "추출상태", "계획안"] if c in df.columns]
            st.dataframe(df[show], hide_index=True, width="stretch")
            pick = st.selectbox("사례 보기", [e["id"] for e in ex], key="ex_pick")
            with st.expander("추출 내용 미리보기"):
                st.text(examples.load_text(pick)[:5000])
            if st.button("이 사례 삭제"):
                examples.delete(pick)
                st.rerun()
        st.divider()
        ups = st.file_uploader("과거 결과보고 추가(.hwp/.hwpx/.pdf/.docx)", accept_multiple_files=True,
                               type=["hwp", "hwpx", "pdf", "docx"], key="ex_up")
        if st.button("사례 등록", disabled=not ups):
            tmpd = Path(tempfile.mkdtemp())
            prog = st.progress(0.0)
            for i, u in enumerate(ups, 1):
                f = tmpd / u.name
                f.write_bytes(u.getvalue())
                m = examples.register(f, "aiboot_result_v1", work_dir=tmpd)
                st.write(f"- {u.name}: {m['추출상태']} ({m['추출경로']})")
                prog.progress(i / len(ups))
            st.info("문체 프로필 탭에서 [다시 생성]을 누르면 새 사례가 반영됩니다.")

    with t3:
        st.markdown(style.load() or "_아직 없음_")
        label = "다시 생성 (Claude 분석)" if config.has_api_key() else "다시 생성 (코드 통계만 — AI 미연결)"
        if st.button(label):
            with st.spinner("분석 중..."):
                style.build(use_ai=True, log_dir=config.path("library") / "logs")
            st.rerun()
