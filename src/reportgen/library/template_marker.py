"""빈 양식 필드 자동 제안 (LIB-04 / F-02, 권장 기능).

표에서 '라벨 셀 | 빈 셀' 구조를 찾아 {{라벨}} 후보를 제안하고, 확인 후 마킹된 사본을 만든다.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..render.hwpx_core import HP, MARKER_RE, HwpxDoc, para_text, set_para_text


def _label(text: str) -> str:
    return re.sub(r"[\s:：·]+", "", text)[:20]


def propose(hwpx_path: str | Path) -> list[dict]:
    """빈 입력 칸 후보 목록: {table, row, col, label}"""
    doc = HwpxDoc.load(hwpx_path)
    out = []
    for root in doc.sections():
        for ti, tbl in enumerate(root.iter(f"{HP}tbl")):
            for tr in tbl.findall(f"{HP}tr"):
                tcs = tr.findall(f"{HP}tc")
                for a, b in zip(tcs, tcs[1:]):
                    la = "".join(para_text(p) for p in a.iter(f"{HP}p")).strip()
                    lb = "".join(para_text(p) for p in b.iter(f"{HP}p")).strip()
                    if la and not lb and len(la) <= 15 and not MARKER_RE.search(la):
                        addr = b.find(f"{HP}cellAddr")
                        out.append({"table": ti, "row": int(addr.get("rowAddr")), "col": int(addr.get("colAddr")),
                                    "label": _label(la)})
    return out


def apply(hwpx_path: str | Path, out_path: str | Path, picks: list[dict]) -> Path:
    """선택된 후보 칸에 {{label}} 을 써 넣은 사본 저장."""
    doc = HwpxDoc.load(hwpx_path)
    want = {(p["table"], p["row"], p["col"]): p["label"] for p in picks}
    for root in doc.sections():
        for ti, tbl in enumerate(root.iter(f"{HP}tbl")):
            for tc in tbl.iter(f"{HP}tc"):
                addr = tc.find(f"{HP}cellAddr")
                key = (ti, int(addr.get("rowAddr")), int(addr.get("colAddr")))
                if key in want:
                    p = tc.find(f"{HP}subList").find(f"{HP}p")
                    set_para_text(p, "{{%s}}" % want[key])
    return doc.save(out_path)
