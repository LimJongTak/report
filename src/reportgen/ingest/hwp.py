"""HWP(바이너리) 추출 (ING-03).

1순위: 한컴오피스 자동화로 .hwpx 변환 → hwpx 추출(표 구조 유지)
2순위: pyhwp(hwp5txt)로 텍스트만 추출
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from .. import config, hancom
from . import hwpx as hwpx_reader
from .base import Block, ExtractedDoc


def extract(path: str | Path, work_dir: str | Path | None = None) -> ExtractedDoc:
    path = Path(path)
    if config.get("ingest.hwp_prefer_hancom", True) and hancom.available():
        out_dir = Path(work_dir) if work_dir else Path(tempfile.mkdtemp())
        dst = out_dir / (path.stem + ".hwpx")
        if hancom.hwp_to_hwpx(path, dst).get("ok"):
            doc = hwpx_reader.extract(dst, method="한컴→hwpx 변환")
            doc.file, doc.type = path.name, "hwp"
            doc.meta["converted_hwpx"] = str(dst)
            return doc
    exe = Path(sys.executable).with_name("hwp5txt.exe")
    doc = ExtractedDoc(file=path.name, type="hwp", method="pyhwp(텍스트만)")
    try:
        cp = subprocess.run([str(exe) if exe.exists() else "hwp5txt", str(path)], capture_output=True, timeout=120)
        text = cp.stdout.decode("utf-8", errors="replace")
    except Exception as e:  # noqa: BLE001
        text = ""
        doc.warnings.append(f"hwp5txt 실행 실패: {e}")
    if text.strip():
        doc.blocks.append(Block(kind="text", content=text.strip(), loc="본문"))
    doc.warnings.append("표 구조 없이 텍스트만 추출됨. 한컴에서 .hwpx로 저장해 다시 올리면 표 인식이 정확해집니다.")
    return doc
