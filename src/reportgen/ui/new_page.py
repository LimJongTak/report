"""S2 새 결과보고: 프로젝트 생성/선택, 파일 업로드, 추출→구조화→초안."""
from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from .. import config, ingest, pipeline, project
from ..generate import drafter
from ..library import templates
from . import common


def _project_box():
    st.subheader("① 프로젝트")
    plist = project.list_projects()
    tl = templates.list_templates()
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**기존 프로젝트 열기**")
        if plist:
            labels = {p["id"]: f"{p.get('name')} ({p['id']})" for p in plist}
            cur = common.current()
            ids = list(labels)
            idx = ids.index(cur.id) if cur and cur.id in ids else 0
            pid = st.selectbox("프로젝트", ids, index=idx, format_func=labels.get, label_visibility="collapsed")
            if st.button("열기"):
                common.set_current(pid)
                st.rerun()
        else:
            st.caption("아직 프로젝트가 없습니다.")
    with c2:
        st.markdown("**새 프로젝트 만들기**")
        name = st.text_input("사업(행사)명", placeholder="예: 2026 네이버클라우드 사옥투어 현장견학")
        date = st.date_input("행사일(파일명에 사용)", value=dt.date.today())
        tid = st.selectbox("사용 양식", [t["id"] for t in tl], format_func=lambda i: next(t["name"] for t in tl if t["id"] == i)) if tl else None
        if st.button("만들기", type="primary", disabled=not (name and tid)):
            p = project.create(name, tid, date.isoformat())
            common.set_current(p.id)
            st.rerun()


def _files_box(p: project.Project):
    st.subheader("② 자료 올리기")
    exts = sorted(e.lstrip(".") for e in ingest.SUPPORTED)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**계획안** (기안문, 운영계획 등 1개 이상)")
        ups = st.file_uploader("계획안", type=exts, accept_multiple_files=True, key=f"plan_up_{p.id}_{st.session_state.get('upk', 0)}", label_visibility="collapsed")
        if ups:
            for u in ups:
                p.add_file(u.getvalue(), u.name, "plan")
            st.session_state["upk"] = st.session_state.get("upk", 0) + 1
            st.rerun()
        for f in p.files("plan"):
            cc1, cc2 = st.columns([5, 1])
            cc1.write(f"📄 {f.name}")
            if cc2.button("삭제", key=f"rmp_{f.name}"):
                p.remove_file(f.name, "plan")
                st.rerun()
    with c2:
        st.markdown("**결과 자료** (명단·지출내역·설문 결과·메모·사진)")
        ups = st.file_uploader("자료", type=exts, accept_multiple_files=True, key=f"mat_up_{p.id}_{st.session_state.get('upk', 0)}", label_visibility="collapsed")
        if ups:
            for u in ups:
                p.add_file(u.getvalue(), u.name, "materials")
            st.session_state["upk"] = st.session_state.get("upk", 0) + 1
            st.rerun()
        for f in p.files("materials"):
            cc1, cc2 = st.columns([5, 1])
            cc1.write(f"{'🖼️' if f.suffix.lower() in ingest.IMAGE_EXT else '📄'} {f.name}")
            if cc2.button("삭제", key=f"rmm_{f.name}"):
                p.remove_file(f.name, "materials")
                st.rerun()


def _run_box(p: project.Project):
    st.subheader("③ 자동 작성")
    mask = st.toggle("AI 전송 전 개인정보 마스킹(이름·전화·이메일·학번)", value=bool(p.meta.get("mask", True)))
    if mask != p.meta.get("mask"):
        p.update_meta(mask=mask)
    st.caption("AI로 보내는 자료: 계획안·결과자료에서 추출한 글자와 표(마스킹 적용), 과거 사례 문단, 문체 프로필. "
               "사진 원본과 마스킹 치환표는 보내지 않습니다. 모든 파일은 이 PC에만 저장됩니다.")
    if not (p.files("plan") or p.files("materials")):
        st.info("자료를 먼저 올려 주세요.")
        return
    if st.button("1) 추출", width="content"):
        bar = st.progress(0.0, "추출 중...")
        pipeline.extract_all(p, progress=lambda i, n, f: bar.progress(i / n, f"추출: {f}"))
        st.session_state["extracted_ok"] = True
    docs = ingest.load_extracted(p.extracted_dir)
    if docs:
        rows = [{"파일": d.file, "구분": "계획안" if d.role == "plan" else "자료", "추출 경로": d.method,
                 "블록 수": len(d.blocks), "경고": " / ".join(d.warnings)} for d in docs]
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        est = pipeline.estimate(p)
        if config.has_api_key():
            st.caption(f"예상 사용량: 입력 약 {est['input_tokens']:,}토큰, 출력 약 {est['output_tokens']:,}토큰, "
                       f"약 ${est['usd']} (AI 작성 필드 {est['ai_fields']}개)")
        c1, c2, c3 = st.columns(3)
        if c1.button("2) 구조화 (계획·실적·비교)"):
            with st.spinner("계획안과 결과 자료를 정리하는 중..."):
                try:
                    pipeline.structure(p)
                    st.success("구조화 완료")
                except Exception as e:  # noqa: BLE001
                    st.error(f"구조화 실패: {e}")
        if p.read_json("comparison.json"):
            force = c3.checkbox("수정·확정한 필드도 다시 생성", value=False)
            if c2.button("3) 초안 생성", type="primary"):
                bar = st.progress(0.0, "초안 생성 중...")
                drafter.generate_all(p, force=force, progress=lambda i, n, k: bar.progress(i / n, f"작성: {k}"))
                st.success("초안을 만들었습니다. '3. 검토'로 이동하세요.")
        cmp_ = p.read_json("comparison.json")
        if cmp_:
            with st.expander("구조화 결과 보기", expanded=False):
                st.markdown("**계획 대비 실적 (코드 계산)**")
                st.dataframe(pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")} for r in cmp_["rows"]]),
                             hide_index=True, width="stretch")
                st.markdown("**plan.json**")
                st.json({k: v for k, v in (p.read_json("plan.json") or {}).items() if k != "_code"}, expanded=False)
                st.markdown("**actual.json**")
                st.json({k: v for k, v in (p.read_json("actual.json") or {}).items() if k != "_code"}, expanded=False)


def render():
    st.title("📥 새 결과보고")
    _project_box()
    p = common.current()
    if not p:
        return
    st.divider()
    _files_box(p)
    st.divider()
    _run_box(p)
