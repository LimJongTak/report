"""TXT/MD 추출 (ING-02)."""
from __future__ import annotations

from pathlib import Path

from .base import Block, ExtractedDoc


def extract(path: str | Path) -> ExtractedDoc:
    raw = Path(path).read_bytes()
    text = None
    for enc in ("utf-8-sig", "cp949"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    text = text if text is not None else raw.decode("utf-8", errors="replace")
    out = ExtractedDoc(file=Path(path).name, type=Path(path).suffix.lstrip("."), method="text")
    out.blocks.append(Block(kind="text", content=text.strip(), loc="본문"))
    return out
