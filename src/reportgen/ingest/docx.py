"""DOCX 추출 (ING-02)."""
from __future__ import annotations

from pathlib import Path

import docx

from .base import Block, ExtractedDoc, rows_to_markdown


def extract(path: str | Path) -> ExtractedDoc:
    d = docx.Document(str(path))
    out = ExtractedDoc(file=Path(path).name, type="docx", method="python-docx")
    paras = [p.text for p in d.paragraphs if p.text.strip()]
    if paras:
        out.blocks.append(Block(kind="text", content="\n".join(paras), loc="본문"))
    for i, t in enumerate(d.tables, 1):
        rows = [[c.text for c in r.cells] for r in t.rows]
        out.blocks.append(Block(kind="table", content=rows_to_markdown(rows), loc=f"표{i}", rows=rows))
    return out
