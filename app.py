"""ReportGen — Streamlit 진입점 (F-17).

실행: run.bat 더블클릭 또는 `streamlit run app.py`
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

import streamlit as st  # noqa: E402

from reportgen.ui import common, library_page, new_page, output_page, review_page  # noqa: E402

st.set_page_config(page_title="ReportGen 결과보고 자동생성", page_icon="📝", layout="wide")

pages = [
    st.Page(library_page.render, title="1. 라이브러리", icon="📚", url_path="library"),
    st.Page(new_page.render, title="2. 새 결과보고", icon="📥", url_path="new", default=True),
    st.Page(review_page.render, title="3. 검토", icon="✏️", url_path="review"),
    st.Page(output_page.render, title="4. 출력", icon="📄", url_path="output"),
]
nav = st.navigation(pages)
common.sidebar()
nav.run()
