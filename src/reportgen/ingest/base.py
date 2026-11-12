"""추출 결과 공통 모델 (ING-06)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Block(BaseModel):
    kind: Literal["text", "table", "image"]
    content: str
    loc: str = ""               # "p.3", "Sheet1!A1:D10", "표2" 등
    rows: list[list[str]] | None = None   # 표 원본 셀(시트/표인 경우)


class ExtractedDoc(BaseModel):
    file: str
    type: str
    method: str = ""            # 사용한 추출 경로 (예: 한컴→hwpx, pyhwp, pdfplumber)
    role: str = "material"      # plan | material
    warnings: list[str] = Field(default_factory=list)
    meta: dict = Field(default_factory=dict)
    blocks: list[Block] = Field(default_factory=list)

    def to_markdown(self) -> str:
        out = [f"# {self.file}", f"- 형식: {self.type} / 추출: {self.method}"]
        out += [f"- ⚠ {w}" for w in self.warnings]
        for b in self.blocks:
            tag = f"[{b.loc}] " if b.loc else ""
            if b.kind == "table":
                out.append(f"\n{tag}(표)\n{b.content}")
            elif b.kind == "image":
                out.append(f"\n{tag}(이미지) {b.content}")
            else:
                out.append(f"\n{tag}{b.content}")
        return "\n".join(out) + "\n"

    def text(self) -> str:
        return "\n".join(b.content for b in self.blocks if b.kind != "image")


def rows_to_markdown(rows: list[list[str]]) -> str:
    """2차원 셀 → 마크다운 표."""
    if not rows:
        return ""
    w = max(len(r) for r in rows)
    rows = [[(c or "").replace("\n", " ").replace("|", "/").strip() for c in r] + [""] * (w - len(r)) for r in rows]
    lines = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * w]
    lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(lines)
