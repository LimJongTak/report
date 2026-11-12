"""분석 공통: 추출 원문 조립 + 마스킹."""
from __future__ import annotations

from ..ingest.base import ExtractedDoc
from ..privacy import Masker


def docs_to_prompt(docs: list[ExtractedDoc], masker: Masker, max_chars: int = 60000) -> str:
    """파일명·위치 표시가 붙은 원문(마스킹 적용). 근거(sources) 기록에 사용."""
    for d in docs:
        for b in d.blocks:
            if b.rows:
                masker.learn_names_from_rows(b.rows)
    parts = []
    for d in docs:
        parts.append(f"\n<<<파일: {d.file}>>>")
        for b in d.blocks:
            if b.kind == "image":
                parts.append(f"[{b.loc}] (사진) {b.content}")
            else:
                parts.append(f"[{b.loc}]\n{b.content}")
    text = masker.mask("\n".join(parts))
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n...(이하 {len(text) - max_chars}자 생략)"
    return text
