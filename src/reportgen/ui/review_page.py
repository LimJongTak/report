"""S3 검토: 필드 목록 / 초안 편집 / 근거·원문, 상단 계획대비실적·검증 경고 (VAL-01)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from .. import ingest
from ..generate import drafter
from ..library import templates
from ..validate import checks
from . import common


def _editor(key: str, ftype: str, fd: dict, field: dict, p):
    v = fd.get("value", "")
    wkey = f"edit_{p.id}_{key}_{st.session_state.get('ver_' + key, 0)}"
    if ftype in ("table", "block"):
        rows = v if isinstance(v, list) else []
        cols = field.get("columns") or (list(rows[0].keys()) if rows else ["값"])
        vis = [c for c in cols if c != "차트"]
        df = pd.DataFrame([{c: r.get(c, "") for c in vis} for r in rows], columns=vis)
        ed = st.data_editor(df, num_rows="dynamic", width="stretch", key=wkey, hide_index=True)
        new = []
        for i, r in enumerate(ed.fillna("").to_dict("records")):
            base = rows[i] if i < len(rows) else {}
            new.append({**base, **{c: str(r.get(c, "")) for c in vis}})
        if "차트" in cols:
            for r in new:
                if r.get("차트") and Path(r["차트"]).exists():
                    st.image(r["차트"], width=320, caption=r.get("문항", ""))
        return new
    if ftype == "image":
        photos = p.photos()
        names = ["(없음)"] + [f.name for f in photos]
        cur = Path(v).name if v else "(없음)"
        pick = st.selectbox("사진 선택", names, index=names.index(cur) if cur in names else 0, key=wkey)
        if pick != "(없음)":
            st.image(str(p.materials_dir / pick), width=360)
            return str(p.materials_dir / pick)
        return ""
    height = 68 if ftype in ("text", "date", "number") else 220
    return st.text_area("내용", value=str(v or ""), height=height, key=wkey, label_visibility="collapsed")


def render():
    st.title("✏️ 검토")
    p = common.need_project()
    if not p:
        return
    schema = templates.load_schema(p.meta["template_id"])
    draft = drafter.load_draft(p)["fields"]
    if not draft:
        st.info("아직 초안이 없습니다. '2. 새 결과보고'에서 [초안 생성]을 실행하세요.")
        return

    cmp_ = p.read_json("comparison.json") or {}
    val = checks.run(p)
    s = val["summary"]
    c = st.columns(5)
    c[0].metric("오류", s["errors"])
    c[1].metric("경고", s["warnings"])
    c[2].metric("[확인 필요]", s["needs_check"])
    c[3].metric("근거 없는 숫자", s["unsupported_numbers"])
    c[4].metric("빈 필수 필드", s["empty_required"])
    with st.expander("계획 대비 실적 (코드 계산)", expanded=False):
        if cmp_.get("rows"):
            st.dataframe(pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")} for r in cmp_["rows"]]),
                         hide_index=True, width="stretch")
    with st.expander(f"검증 경고 {len(val['issues'])}건", expanded=s["errors"] > 0):
        if val["issues"]:
            st.dataframe(pd.DataFrame(val["issues"]).rename(columns={"level": "수준", "field": "필드", "kind": "유형", "detail": "내용"}),
                         hide_index=True, width="stretch")

    left, mid, right = st.columns([1.1, 2.6, 1.6])
    keys = [f["key"] for f in schema["fields"]]
    with left:
        st.markdown("**필드**")

        def label(k):
            fd = draft.get(k, {})
            warn = "⚠️" if (val["fields"].get(k, {}).get("needs_check") or val["fields"].get(k, {}).get("unsupported_numbers")) else ""
            return f"{common.STATUS_ICON.get(fd.get('status'), '·')}{warn} {k}"
        sel = st.radio("필드", keys, format_func=label, label_visibility="collapsed", key="sel_field")
    field = next(f for f in schema["fields"] if f["key"] == sel)
    fd = draft.get(sel, {})
    with mid:
        st.markdown(f"### {sel}  ")
        st.caption(f"유형 {field.get('type')} · 출처 {common.ORIGIN_LABEL.get(fd.get('origin'), '-')} · "
                   f"상태 {fd.get('status', '-')}" + (f" · 가이드: {field['guide']}" if field.get("guide") else ""))
        if fd.get("error"):
            st.error(fd["error"])
        new_val = _editor(sel, field.get("type", "text"), fd, field, p)
        b1, b2 = st.columns(2)
        if b1.button("💾 수정 저장", width="stretch"):
            drafter.update_field(p, sel, new_val, "edited")
            st.toast("저장했습니다")
            st.rerun()
        if b2.button("✅ 확정", width="stretch"):
            drafter.update_field(p, sel, new_val, "confirmed")
            st.rerun()
        if field.get("type") != "image":
            st.markdown("**다시 생성**")
            ins = st.text_input("추가 지시 (예: 더 짧게, 성과 강조, 수치 포함)", key=f"ins_{sel}")
            if st.button("🔄 재생성"):
                with st.spinner("다시 쓰는 중..."):
                    drafter.regenerate(p, sel, ins)
                st.session_state["ver_" + sel] = st.session_state.get("ver_" + sel, 0) + 1
                st.rerun()
    with right:
        st.markdown("**근거**")
        for src in fd.get("sources") or []:
            q = f" — “{src.get('quote')}”" if src.get("quote") else ""
            st.markdown(f"- `{src.get('file', '')}` {src.get('loc', '')}{q}")
        if not fd.get("sources"):
            st.caption("기록된 근거 없음")
        fv = val["fields"].get(sel, {})
        for n in fv.get("unsupported_numbers", []):
            st.warning(f"자료에서 찾지 못한 숫자: {n}")
        for r in fv.get("needs_check", []):
            st.warning(f"확인 필요: {r}")
        st.markdown("**원문 보기**")
        docs = [d for d in ingest.load_extracted(p.extracted_dir) if d.type != "image"]
        if docs:
            names = [d.file for d in docs]
            srcs = [s_.get("file") for s_ in fd.get("sources") or [] if s_.get("file") in names]
            pick = st.selectbox("파일", names, index=names.index(srcs[0]) if srcs else 0, key="src_pick")
            doc = next(d for d in docs if d.file == pick)
            st.text_area("원문", doc.to_markdown()[:20000], height=420, label_visibility="collapsed")
