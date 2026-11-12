"""XLSX/CSV 추출 → 마크다운 표 (ING-02)."""
from __future__ import annotations

import csv
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from .base import Block, ExtractedDoc, rows_to_markdown


def _fmt(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    if hasattr(v, "strftime"):
        has_time = getattr(v, "hour", 0) or getattr(v, "minute", 0)
        return v.strftime("%Y-%m-%d %H:%M" if has_time else "%Y-%m-%d")
    return str(v).strip()


def _trim(rows: list[list[str]]) -> list[list[str]]:
    rows = [r for r in rows if any(c for c in r)]
    if not rows:
        return rows
    w = max(max((i for i, c in enumerate(r) if c), default=-1) for r in rows) + 1
    return [r[:w] for r in rows]


def extract(path: str | Path) -> ExtractedDoc:
    path = Path(path)
    out = ExtractedDoc(file=path.name, type=path.suffix.lstrip(".").lower(), method="openpyxl/csv")
    if path.suffix.lower() == ".csv":
        raw = path.read_bytes()
        text = None
        for enc in ("utf-8-sig", "cp949"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        text = text if text is not None else raw.decode("utf-8", errors="replace")
        rows = _trim([[c.strip() for c in r] for r in csv.reader(text.splitlines())])
        out.blocks.append(Block(kind="table", content=rows_to_markdown(rows), loc=f"{path.name}!A1", rows=rows))
        return out
    wb = load_workbook(path, data_only=True, read_only=True)
    for ws in wb.worksheets:
        rows = _trim([[_fmt(v) for v in r] for r in ws.iter_rows(values_only=True)])
        if not rows:
            continue
        loc = f"{ws.title}!A1:{get_column_letter(max(len(r) for r in rows))}{len(rows)}"
        out.blocks.append(Block(kind="table", content=rows_to_markdown(rows), loc=loc, rows=rows))
    wb.close()
    return out
