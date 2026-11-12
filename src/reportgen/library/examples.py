"""과거 결과보고 등록 (LIB-05, 06, 08, 09 / F-03).

library/examples/<연도_사업명>/
  source.(hwp|hwpx|pdf|docx)   원본 사본
  source.hwpx                  (hwp를 한컴으로 변환한 경우)
  extracted.md                 장(章) 단위로 나눈 본문
  meta.yaml                    연도, 사업명, 사업유형, 양식ID, 추출 경로
  plan.md                      (있으면) 같은 사업의 계획안 — 백테스트용
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

import yaml

from .. import config, ingest

EVENT_TYPES = [
    ("현장견학", ["견학", "투어", "탐방", "방문"]),
    ("경진대회", ["경진대회", "공모전", "해커톤", "대회"]),
    ("특강", ["특강", "초청", "세미나", "강연"]),
    ("워크숍", ["워크숍", "워크샵", "포럼"]),
    ("산학프로젝트", ["프로젝트", "산학"]),
    ("교육과정", ["교육과정", "전문과정", "과정", "부트캠프", "캠프", "교육"]),
]

# 양식 필드 ↔ 과거 보고서의 소제목 키워드 (few-shot 예시 찾기용)
FIELD_ALIASES = {
    "추진배경": ["추진배경", "추진 배경", "배경"],
    "추진목적": ["추진목적", "추진 목적", "목적"],
    "주요추진내용": ["주요 추진내용", "주요내용", "주요 내용", "추진내용"],
    "운영결과": ["운영 성과", "운영성과", "운영 결과", "추진실적", "추진 실적"],
    "성과제목": ["운영 성과", "운영성과"],
    "만족도요약": ["만족도 조사 결과", "만족도"],
    "만족도문항": ["설문:응답자수", "만족도"],
    "주요성과": ["주요 성과", "주요성과", "성과"],
    "향후계획": ["활용", "향후", "개선", "발전방안"],
}


def examples_dir() -> Path:
    return config.path("library") / "examples"


def classify(title: str) -> str:
    for name, kws in EVENT_TYPES:
        if any(k in title for k in kws):
            return name
    return "기타"


def guess_meta(path: Path, text: str) -> dict:
    stem = path.stem
    year = re.search(r"(20\d{2})", stem) or re.search(r"(20\d{2})", text[:500])
    date = re.search(r"(20\d{2})[.\-년\s]+(\d{1,2})[.\-월\s]+(\d{1,2})", stem)
    name = re.sub(r"^\(.*?\)\s*|^붙임\s*\d+\.\s*", "", stem).strip()
    name = re.sub(r"\s*결과\s*보고(서)?$", "", name).strip()
    return {
        "연도": int(year.group(1)) if year else None,
        "일자": f"{date.group(1)}-{int(date.group(2)):02d}-{int(date.group(3)):02d}" if date else None,
        "사업명": name,
        "사업유형": classify(stem + " " + text[:300]),
    }


def _slug(meta: dict) -> str:
    s = f"{meta.get('연도') or '0000'}_{meta['사업명']}"
    return re.sub(r'[\\/:*?"<>|]+', "_", s)[:80]


def register(src: str | Path, template_id: str | None = None, plan: str | Path | None = None,
             work_dir: str | Path | None = None) -> dict:
    """LIB-05 과거 결과보고 1건 등록."""
    src = Path(src)
    doc = ingest.extract(src, work_dir=work_dir)
    meta = guess_meta(src, doc.text())
    d = examples_dir() / _slug(meta)
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, d / ("source" + src.suffix.lower()))
    conv = doc.meta.get("converted_hwpx")
    if conv and Path(conv).exists():
        shutil.copy2(conv, d / "source.hwpx")
    (d / "extracted.md").write_text(doc.to_markdown(), encoding="utf-8")
    readable = bool(doc.text().strip()) and not doc.meta.get("unreadable_pages")
    meta.update({
        "양식ID": template_id,
        "원본파일": src.name,
        "추출경로": doc.method,
        "추출상태": "정상" if readable else "텍스트 없음(원본 hwp/hwpx 필요 또는 API 비전 읽기)",
        "경고": doc.warnings,
    })
    if plan:
        pdoc = ingest.extract(plan, work_dir=work_dir)
        (d / "plan.md").write_text(pdoc.to_markdown(), encoding="utf-8")
        shutil.copy2(plan, d / ("plan_source" + Path(plan).suffix.lower()))
        meta["계획안"] = Path(plan).name
    (d / "meta.yaml").write_text(yaml.safe_dump(meta, allow_unicode=True, sort_keys=False), encoding="utf-8")
    meta["dir"] = str(d)
    return meta


def list_examples() -> list[dict]:
    out = []
    for m in sorted(examples_dir().glob("*/meta.yaml")):
        meta = yaml.safe_load(m.read_text(encoding="utf-8")) or {}
        meta["dir"] = str(m.parent)
        meta["id"] = m.parent.name
        out.append(meta)
    return out


def delete(example_id: str) -> None:
    shutil.rmtree(examples_dir() / example_id, ignore_errors=True)


def load_text(example_id: str) -> str:
    p = examples_dir() / example_id / "extracted.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def snippets(field_key: str, event_type: str | None = None, n: int = 3, max_chars: int = 900) -> list[dict]:
    """LIB-09/GEN-04 같은 필드의 과거 사례 문단 n개(사업유형이 같은 사례 우선)."""
    aliases = FIELD_ALIASES.get(field_key, [field_key])
    exs = [e for e in list_examples() if e.get("추출상태") == "정상"]
    exs.sort(key=lambda e: (e.get("사업유형") != event_type, -(e.get("연도") or 0)))
    out = []
    for e in exs:
        text = load_text(e["id"])
        for a in aliases:
            i = text.find(a)
            if i < 0:
                continue
            chunk = text[i:i + max_chars]
            # 다음 장 제목에서 자르기
            cut = chunk.find("\n## ", len(a))
            if cut > 0:
                chunk = chunk[:cut]
            if len(chunk.strip()) > len(a) + 20:
                out.append({"example": e["사업명"], "type": e.get("사업유형"), "text": chunk.strip()})
                break
        if len(out) >= n:
            break
    return out
