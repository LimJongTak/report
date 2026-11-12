"""PDF 추출 (ING-02). 글꼴 매핑이 깨진(cid) PDF·스캔 PDF는 Claude 비전으로 읽기(옵션)."""
from __future__ import annotations

import re
from pathlib import Path

import pdfplumber

from .. import config
from .base import Block, ExtractedDoc, rows_to_markdown


def is_broken(text: str) -> bool:
    """한글 문서를 PDF로 인쇄할 때 자주 생기는 (cid:NN) 깨짐 또는 텍스트 없음."""
    if not text.strip():
        return True
    cid = len(re.findall(r"\(cid:\d+\)", text))
    return cid > 20 and cid * 7 > len(text) * 0.3


def extract(path: str | Path, use_vision: bool | None = None) -> ExtractedDoc:
    path = Path(path)
    doc = ExtractedDoc(file=path.name, type="pdf", method="pdfplumber")
    broken_pages = []
    with pdfplumber.open(path) as pdf:
        doc.meta["pages"] = len(pdf.pages)
        for i, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            if is_broken(text):
                broken_pages.append(i)
                continue
            doc.blocks.append(Block(kind="text", content=text, loc=f"p.{i}"))
            for k, t in enumerate(page.extract_tables() or [], 1):
                rows = [[c or "" for c in r] for r in t]
                doc.blocks.append(Block(kind="table", content=rows_to_markdown(rows), loc=f"p.{i} 표{k}", rows=rows))
    if broken_pages:
        use_vision = config.get("ingest.pdf_vision_fallback", True) if use_vision is None else use_vision
        if use_vision and config.has_api_key():
            from ..llm import read_pdf_pages
            for i, text in read_pdf_pages(path, broken_pages):
                doc.blocks.append(Block(kind="text", content=text, loc=f"p.{i}(비전)"))
            doc.blocks.sort(key=lambda b: int(re.search(r"\d+", b.loc).group()))
            doc.method += " + Claude 비전"
        else:
            doc.warnings.append(
                f"{len(broken_pages)}개 쪽의 글자를 읽을 수 없습니다(글꼴 매핑 깨짐 또는 스캔본). "
                "원본 .hwp/.hwpx를 올리거나 API 키를 설정해 비전 읽기를 사용하세요."
            )
            doc.meta["unreadable_pages"] = broken_pages
    return doc
