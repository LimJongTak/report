"""파일 추출기 (ING-01~06). extract(path)로 확장자별 리더 자동 선택."""
from __future__ import annotations

from pathlib import Path

from .base import Block, ExtractedDoc

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".gif"}
SUPPORTED = {".hwp", ".hwpx", ".pdf", ".docx", ".xlsx", ".xlsm", ".csv", ".txt", ".md"} | IMAGE_EXT


def extract(path: str | Path, work_dir: str | Path | None = None) -> ExtractedDoc:
    """ING-02 확장자로 리더를 골라 추출."""
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".hwpx":
        from .hwpx import extract as f
        return f(path)
    if ext == ".hwp":
        from .hwp import extract as f
        return f(path, work_dir)
    if ext == ".pdf":
        from .pdf import extract as f
        return f(path)
    if ext == ".docx":
        from .docx import extract as f
        return f(path)
    if ext in (".xlsx", ".xlsm", ".csv"):
        from .sheet import extract as f
        return f(path)
    if ext in (".txt", ".md"):
        from .text import extract as f
        return f(path)
    if ext in IMAGE_EXT:
        from .image import extract as f
        return f(path)
    return ExtractedDoc(file=path.name, type=ext, method="미지원", warnings=[f"지원하지 않는 형식: {ext}"])


def save_extracted(doc: ExtractedDoc, out_dir: str | Path) -> Path:
    """ING-06 work/extracted/<원본파일명>.md (+ .json) 저장."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    md = out_dir / f"{doc.file}.md"
    md.write_text(doc.to_markdown(), encoding="utf-8")
    (out_dir / f"{doc.file}.json").write_text(doc.model_dump_json(indent=1), encoding="utf-8")
    return md


def load_extracted(out_dir: str | Path) -> list[ExtractedDoc]:
    out_dir = Path(out_dir)
    return [ExtractedDoc.model_validate_json(p.read_text(encoding="utf-8")) for p in sorted(out_dir.glob("*.json"))]


__all__ = ["Block", "ExtractedDoc", "extract", "save_extracted", "load_extracted", "SUPPORTED", "IMAGE_EXT"]
