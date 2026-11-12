"""PDF 변환 (OUT-04, OUT-06).

1순위 한컴오피스 자동화 → 2순위 LibreOffice(+H2Orestart 확장). 둘 다 없으면 안내 메시지.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .. import config, hancom

MANUAL_GUIDE = (
    "PDF 자동 변환기를 찾지 못했습니다. 한컴오피스에서 생성된 .hwpx 파일을 열고 "
    "[파일] → [PDF로 저장하기]를 눌러 직접 저장해 주세요."
)


def find_soffice() -> str | None:
    p = config.get("pdf.soffice_path") or ""
    if p and Path(p).exists():
        return p
    for cand in [shutil.which("soffice"), r"C:\Program Files\LibreOffice\program\soffice.exe",
                 r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"]:
        if cand and Path(cand).exists():
            return cand
    return None


def diagnose() -> dict:
    """OUT-04 내 PC에서 사용 가능한 변환기 진단."""
    h = hancom.probe()
    s = find_soffice()
    return {
        "hancom": {"ok": bool(h.get("ok")), "detail": h.get("version") or h.get("error")},
        "libreoffice": {"ok": bool(s), "detail": s or "설치 안 됨 (H2Orestart 확장도 필요)"},
    }


def to_pdf(hwpx: str | Path, pdf: str | Path | None = None) -> dict:
    """OUT-04 hwpx → pdf. 반환 {ok, path, converter, message}"""
    hwpx = Path(hwpx)
    pdf = Path(pdf) if pdf else hwpx.with_suffix(".pdf")
    errors = []
    for conv in config.get("pdf.converters", ["hancom", "libreoffice"]):
        if conv == "hancom":
            r = hancom.to_pdf(hwpx, pdf)
            if r.get("ok"):
                return {"ok": True, "path": str(pdf), "converter": "한컴오피스", "message": ""}
            errors.append(f"한컴: {r.get('error', '실패')}")
        elif conv == "libreoffice":
            s = find_soffice()
            if not s:
                errors.append("LibreOffice: 설치 안 됨")
                continue
            try:
                subprocess.run([s, "--headless", "--convert-to", "pdf", "--outdir", str(pdf.parent), str(hwpx)],
                               capture_output=True, timeout=180)
                produced = pdf.parent / (hwpx.stem + ".pdf")
                if produced.exists():
                    if produced != pdf:
                        produced.replace(pdf)
                    return {"ok": True, "path": str(pdf), "converter": "LibreOffice", "message": ""}
                errors.append("LibreOffice: 변환 실패(H2Orestart 확장 설치 여부 확인)")
            except Exception as e:  # noqa: BLE001
                errors.append(f"LibreOffice: {e}")
    return {"ok": False, "path": None, "converter": None, "message": MANUAL_GUIDE + "\n(" + "; ".join(errors) + ")"}
