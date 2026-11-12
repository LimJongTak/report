"""이미지 메타 추출 (ING-04). 촬영일시(EXIF)·크기 기록, 사진 필드 후보로 등록."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from .base import Block, ExtractedDoc


def extract(path: str | Path) -> ExtractedDoc:
    path = Path(path)
    out = ExtractedDoc(file=path.name, type="image", method="Pillow")
    with Image.open(path) as im:
        w, h = im.size
        taken = ""
        try:
            exif = im.getexif()
            taken = exif.get_ifd(0x8769).get(36867) or exif.get(306) or ""
        except Exception:  # noqa: BLE001
            pass
    out.meta = {"width": w, "height": h, "taken": str(taken), "photo_candidate": True}
    out.blocks.append(Block(kind="image", content=f"{path.name} ({w}x{h}, 촬영 {taken or '정보 없음'})", loc="이미지"))
    return out
