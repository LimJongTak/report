"""UI 공통: 현재 프로젝트 상태(새로고침해도 유지 — URL ?p=프로젝트ID)."""
from __future__ import annotations

import streamlit as st

from .. import config, project


def current() -> project.Project | None:
    pid = st.session_state.get("project_id") or st.query_params.get("p")
    if not pid:
        return None
    try:
        p = project.open_project(pid)
    except FileNotFoundError:
        return None
    st.session_state["project_id"] = pid
    return p


def set_current(pid: str | None) -> None:
    st.session_state["project_id"] = pid
    if pid:
        st.query_params["p"] = pid
    elif "p" in st.query_params:
        del st.query_params["p"]


def sidebar() -> None:
    with st.sidebar:
        st.markdown("### 📝 ReportGen")
        p = current()
        if p:
            st.success(f"작업 중: **{p.meta.get('name')}**")
            st.caption(p.id)
        else:
            st.info("'2. 새 결과보고'에서 프로젝트를 만들거나 여세요.")
        if config.has_api_key():
            st.caption(f"AI: 연결됨 · {config.get('llm.model')}")
        else:
            st.warning("AI 미연결: .env에 ANTHROPIC_API_KEY를 넣으면 초안 문장을 AI가 작성합니다. "
                       "지금은 자료·숫자 항목만 자동으로 채워집니다.")


def need_project() -> project.Project | None:
    p = current()
    if not p:
        st.warning("먼저 '2. 새 결과보고'에서 프로젝트를 만들거나 선택하세요.")
    return p


STATUS_ICON = {"draft": "📝", "edited": "✏️", "confirmed": "✅", "error": "❌"}
ORIGIN_LABEL = {"data": "자료·계산", "ai": "AI", "user": "직접 작성", "empty": "비어 있음"}
