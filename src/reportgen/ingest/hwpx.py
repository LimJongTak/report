"""HWPX 텍스트·표 추출 (ING-02)."""
from __future__ import annotations

from pathlib import Path

from ..render.hwpx_core import HP, HwpxDoc, para_text
from .base import Block, ExtractedDoc, rows_to_markdown


def _cell_text(tc) -> str:
    sl = tc.find(f"{HP}subList")
    return "\n".join(para_text(p) for p in sl.findall(f"{HP}p")) if sl is not None else ""


def table_rows(tbl) -> list[list[str]]:
    rows = int(tbl.get("rowCnt", 0))
    cols = int(tbl.get("colCnt", 0))
    grid = [["" for _ in range(cols)] for _ in range(rows)]
    for tr in tbl.findall(f"{HP}tr"):
        for tc in tr.findall(f"{HP}tc"):
            a = tc.find(f"{HP}cellAddr")
            r, c = int(a.get("rowAddr")), int(a.get("colAddr"))
            if r < rows and c < cols:
                grid[r][c] = _cell_text(tc)
    return grid


def extract(path: str | Path, method: str = "hwpx") -> ExtractedDoc:
    doc = HwpxDoc.load(path)
    out = ExtractedDoc(file=Path(path).name, type="hwpx", method=method)
    n_tbl = 0
    for si, root in enumerate(doc.sections()):
        buf: list[str] = []

        def flush():
            if any(x.strip() for x in buf):
                out.blocks.append(Block(kind="text", content="\n".join(x for x in buf if x.strip()), loc=f"구역{si + 1}"))
            buf.clear()

        for p in root.findall(f"{HP}p"):
            t = para_text(p)
            if t.strip():
                buf.append(t.strip())
            for run in p.findall(f"{HP}run"):
                for tbl in run.findall(f"{HP}tbl"):
                    flush()
                    n_tbl += 1
                    rows = table_rows(tbl)
                    if len(rows) == 1 and len(rows[0]) <= 2:   # 장 제목 상자
                        out.blocks.append(Block(kind="text", content="## " + " ".join(c.strip() for c in rows[0] if c.strip()), loc=f"표{n_tbl}"))
                    else:
                        out.blocks.append(Block(kind="table", content=rows_to_markdown(rows), loc=f"표{n_tbl}", rows=rows))
                if run.findall(f"{HP}pic"):
                    buf.append("[그림]")
        flush()
    return out
