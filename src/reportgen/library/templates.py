"""양식 등록·필드 추출·schema.yaml (LIB-01~03, F-01).

schema.yaml 필드 속성
- key, type(text|paragraph|table|block|image|date|number), required, guide, max_chars
- binding : 코드가 채울 데이터 경로. 'actual.장소|plan.장소' 처럼 | 로 대체 경로. 없으면 AI가 작성
- columns : table/block의 열(하위 필드)
- ai_subfields : block에서 AI가 쓸 하위 필드
- line_prefix : 여러 줄 값의 각 줄 앞에 붙일 문자열
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

import yaml

from .. import config
from ..render.hwpx_core import HP, MARKER_RE, HwpxDoc, ancestor, normalize_markers, para_text


def templates_dir() -> Path:
    return config.path("library") / "templates"


def list_templates() -> list[dict]:
    out = []
    for d in sorted(templates_dir().glob("*/schema.yaml")):
        s = yaml.safe_load(d.read_text(encoding="utf-8")) or {}
        out.append({"id": s.get("template_id", d.parent.name), "name": s.get("name", d.parent.name),
                    "fields": len(s.get("fields", [])), "dir": str(d.parent)})
    return out


def load_schema(template_id: str) -> dict:
    return yaml.safe_load((templates_dir() / template_id / "schema.yaml").read_text(encoding="utf-8"))


def save_schema(template_id: str, schema: dict) -> None:
    (templates_dir() / template_id / "schema.yaml").write_text(
        yaml.safe_dump(schema, allow_unicode=True, sort_keys=False, width=200), encoding="utf-8")


def template_path(template_id: str) -> Path:
    return templates_dir() / template_id / "template.hwpx"


def extract_fields(hwpx_path: str | Path) -> list[dict]:
    """LIB-02 양식 안의 마커를 찾아 필드 목록 생성(유형 추정 포함)."""
    doc = HwpxDoc.load(hwpx_path)
    fields: dict[str, dict] = {}
    order: list[str] = []

    def add(key, **kw):
        if key not in fields:
            fields[key] = {"key": key, **kw}
            order.append(key)
        return fields[key]

    for root in doc.sections():
        normalize_markers(root)
        # 표 반복 행
        repeat_cols: dict[str, list[str]] = {}
        for tc in root.iter(f"{HP}tc"):
            txt = "".join(para_text(p) for p in tc.iter(f"{HP}p"))
            m = re.search(r"\{\{#([^{}]+?)\}\}", txt)
            if m:
                tr = tc.getparent()
                cols = [mm.group(2).strip() for p in tr.iter(f"{HP}p") for mm in MARKER_RE.finditer(para_text(p)) if not mm.group(1)]
                repeat_cols[m.group(1).strip()] = cols
                for x in tr.iter(f"{HP}p"):
                    x.set("_rg_rep", "1")
                add(m.group(1).strip(), type="table", columns=cols)
        # 블록 반복
        cur_block = None
        for p in root.iter(f"{HP}p"):
            t = para_text(p)
            in_cell = ancestor(p, f"{HP}tc") is not None
            for m in MARKER_RE.finditer(t):
                flag, key = m.group(1), m.group(2).strip()
                if flag == "#" and not in_cell:
                    cur_block = key
                    add(key, type="block", columns=[])
                elif flag == "/":
                    if cur_block == key:
                        p.set("_rg_blk", key)
                    cur_block = None if cur_block == key else cur_block
            if cur_block:
                p.set("_rg_blk", cur_block)
        for p in root.iter(f"{HP}p"):
            t = para_text(p)
            in_cell = ancestor(p, f"{HP}tc") is not None
            blk = p.get("_rg_blk")
            for m in MARKER_RE.finditer(t):
                flag, key = m.group(1), m.group(2).strip()
                if flag:
                    continue
                if blk:
                    if key not in fields[blk]["columns"]:
                        fields[blk]["columns"].append(key)
                    continue
                if p.get("_rg_rep"):
                    continue
                solo = t.strip() == m.group(0)
                bf = None
                tc = ancestor(p, f"{HP}tc")
                if tc is not None:
                    b = doc.border_fill(tc.get("borderFillIDRef"))
                    bf = b is not None and b.find(".//{http://www.hancom.co.kr/hwpml/2011/core}imgBrush") is not None
                if bf:
                    add(key, type="image")
                elif solo and not in_cell:
                    add(key, type="paragraph")
                else:
                    add(key, type="text")
        for pic in root.iter(f"{HP}pic"):
            sc = pic.find(f"{HP}shapeComment")
            if sc is not None and sc.text:
                for m in MARKER_RE.finditer(sc.text):
                    key = m.group(2).strip()
                    blk = ancestor(pic, f"{HP}p").get("_rg_blk")
                    if blk:
                        if key not in fields[blk]["columns"]:
                            fields[blk]["columns"].append(key)
                    else:
                        add(key, type="image")
    out = []
    for k in order:
        f = fields[k]
        if f["type"] in ("table", "block") and not f.get("columns"):
            f.pop("columns", None)
        out.append(f)
    return out


def register(hwpx_path: str | Path, template_id: str, name: str | None = None,
             hints: dict | None = None, original: str | Path | None = None) -> dict:
    """LIB-01 양식 등록: template.hwpx/original 복사, schema.yaml 생성.

    hints: {키: {속성}} — 기존 schema나 기본값을 덮어씌움(사용자 편집 보존)
    """
    d = templates_dir() / template_id
    d.mkdir(parents=True, exist_ok=True)
    src = Path(hwpx_path)
    if src.resolve() != (d / "template.hwpx").resolve():
        shutil.copy2(src, d / "template.hwpx")
    if original:
        shutil.copy2(original, d / ("original" + Path(original).suffix))
    elif not list(d.glob("original.*")):
        shutil.copy2(src, d / "original.hwpx")
    old = {}
    if (d / "schema.yaml").exists():
        old = {f["key"]: f for f in (load_schema(template_id).get("fields") or [])}
    hints = hints or {}
    fields = []
    for f in extract_fields(d / "template.hwpx"):
        merged = {**f, "required": True, **hints.get(f["key"], {}), **{k: v for k, v in old.get(f["key"], {}).items() if k not in ("type", "columns")}}
        fields.append(merged)
    schema = {"template_id": template_id, "name": name or template_id, "fields": fields}
    save_schema(template_id, schema)
    return schema


def delete(template_id: str) -> None:
    shutil.rmtree(templates_dir() / template_id, ignore_errors=True)
