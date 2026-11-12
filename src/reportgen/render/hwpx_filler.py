"""양식 HWPX 채우기 (OUT-01~03, 기능정의서 7장 5~6번).

마커 규칙
- `{{키}}`                     : 텍스트. 문단에 마커만 있으면 값의 줄바꿈(\n)마다 문단을 복제(문단모양 유지)
- 표 셀 안 `{{#키}}`           : 그 행을 데이터 행 수만큼 복제. 행 안의 `{{열이름}}` 치환
- 문단 `{{#키}}` ... `{{/키}}` : 문단 묶음(블록)을 항목 수만큼 복제
- 그림 설명(shapeComment) `{{키}}` : 그림 이미지 교체 (없으면 그림 제거)
- 배경그림이 있는 표 셀 안 `{{키}}` : 셀 배경 이미지 교체 (사진 칸)

치환 순서: ① run 정규화 → ② 표 반복 행 → ③ 블록 반복 → ④ 텍스트(여러 줄) 치환 → ⑤ 이미지 → ⑥ 저장
"""
from __future__ import annotations

import copy
import io
import re
from pathlib import Path
from typing import Any

from lxml import etree
from PIL import Image, ImageOps

from .hwpx_core import (
    HC, HH, HP, HWPUNIT_PER_PX, MARKER_RE, HwpxDoc, ancestor, mark_dirty,
    normalize_markers, para_text, set_para_text, _segments, _seg_get, _seg_set,
)


class FillResult(dict):
    """fill() 결과: remaining(남은 마커), warnings"""


def _to_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (list, tuple)):
        return "\n".join(_to_str(x) for x in v)
    return str(v)


# ---------------- ② 표 반복 행 ----------------

def _fill_table_rows(root, data: dict, images: dict, warnings: list) -> None:
    while True:
        target = None
        for tc in root.iter(f"{HP}tc"):
            m = re.search(r"\{\{#([^{}]+?)\}\}", "".join(para_text(p) for p in tc.iter(f"{HP}p")))
            if m:
                target = (tc, m.group(1).strip())
                break
        if not target:
            return
        tc, key = target
        tr = tc.getparent()
        tbl = tr.getparent()
        rows = data.get(key) or []
        if not isinstance(rows, list):
            warnings.append(f"표 필드 '{key}' 값이 목록이 아님")
            rows = []
        pos = tbl.index(tr)
        row_h = _row_height(tr)
        for i, item in enumerate(rows):
            clone = copy.deepcopy(tr)
            _strip_repeat_marker(clone, key)
            item = item if isinstance(item, dict) else {"값": item}
            for p in list(clone.iter(f"{HP}p")):
                _substitute_para(p, item, images, prefix=f"{key}[{i}].")
            tbl.insert(pos + i, clone)
        tbl.remove(tr)
        _renumber_table(tbl, delta_rows=len(rows) - 1, row_h=row_h)


def _strip_repeat_marker(el, key: str) -> None:
    pat = re.compile(r"\{\{#\s*" + re.escape(key) + r"\s*\}\}")
    for p in el.iter(f"{HP}p"):
        for s in _segments(p):
            t = _seg_get(s)
            if pat.search(t):
                _seg_set(s, pat.sub("", t))
                mark_dirty(p)


def _row_height(tr) -> int:
    hs = [int(sz.get("height", 0)) for sz in tr.iter(f"{HP}cellSz")]
    return max(hs) if hs else 0


def _renumber_table(tbl, delta_rows: int, row_h: int) -> None:
    trs = tbl.findall(f"{HP}tr")
    for r, tr in enumerate(trs):
        for tc in tr.findall(f"{HP}tc"):
            addr = tc.find(f"{HP}cellAddr")
            if addr is not None:
                addr.set("rowAddr", str(r))
    tbl.set("rowCnt", str(len(trs)))
    sz = tbl.find(f"{HP}sz")
    if sz is not None and row_h:
        sz.set("height", str(max(row_h, int(sz.get("height", 0)) + delta_rows * row_h)))


# ---------------- ③ 블록 반복 ----------------

def _fill_blocks(root, data: dict, images: dict, warnings: list) -> None:
    while True:
        found = None
        for p in root.iter(f"{HP}p"):
            m = re.search(r"\{\{#([^{}]+?)\}\}", para_text(p))
            if m and ancestor(p, f"{HP}tc") is None:
                found = (p, m.group(1).strip())
                break
        if not found:
            return
        start, key = found
        parent = start.getparent()
        sibs = list(parent)
        i0 = sibs.index(start)
        end_pat = re.compile(r"\{\{/\s*" + re.escape(key) + r"\s*\}\}")
        i1 = next((j for j in range(i0, len(sibs)) if sibs[j].tag == f"{HP}p" and end_pat.search(para_text(sibs[j]))), i0)
        block = sibs[i0:i1 + 1]
        items = data.get(key) or []
        if not isinstance(items, list):
            warnings.append(f"블록 필드 '{key}' 값이 목록이 아님")
            items = []
        for n, item in enumerate(items):
            item = item if isinstance(item, dict) else {"값": item}
            for el in block:
                clone = copy.deepcopy(el)
                _strip_repeat_marker(clone, key)
                for p in clone.iter(f"{HP}p"):
                    for s in _segments(p):
                        t = _seg_get(s)
                        if end_pat.search(t):
                            _seg_set(s, end_pat.sub("", t))
                for pic in clone.iter(f"{HP}pic"):
                    _rename_pic_marker(pic, item, images, f"{key}[{n}].")
                parent.insert(parent.index(start), clone)
                # 블록 안 문단: 여러 줄 값 처리 포함 (삽입 후 치환해야 문단 복제 가능)
                for p in list(clone.iter(f"{HP}p")):
                    _substitute_para(p, item, images, prefix=f"{key}[{n}].")
        for el in block:
            parent.remove(el)


def _rename_pic_marker(pic, item: dict, images: dict, prefix: str) -> None:
    sc = pic.find(f"{HP}shapeComment")
    if sc is None or not sc.text:
        return

    def repl(m):
        name = m.group(2).strip()
        if name in item:
            images[prefix + name] = item[name]
            return "{{" + prefix + name + "}}"
        return m.group(0)

    sc.text = MARKER_RE.sub(repl, sc.text)


# ---------------- ④ 텍스트 치환 ----------------

def _substitute_para(p, data: dict, images: dict, prefix: str = "") -> None:
    """문단 하나의 마커 치환. 마커 하나만 있는 문단 + 여러 줄 값이면 문단 복제."""
    txt = para_text(p)
    if "{{" not in txt:
        return
    solo = MARKER_RE.fullmatch(txt.strip())
    if solo and not solo.group(1):
        key = solo.group(2).strip()
        if key in data and _is_image_value(data[key]) and ancestor(p, f"{HP}tc") is not None:
            images[prefix + key] = data[key]
            set_para_text(p, "{{" + prefix + key + "}}")
            return
        if key in data and not isinstance(data[key], (dict,)):
            lines = _to_str(data[key]).split("\n")
            parent = p.getparent()
            pos = parent.index(p)
            set_para_text(p, lines[0])
            for k, line in enumerate(lines[1:], start=1):
                clone = copy.deepcopy(p)
                set_para_text(clone, line)
                parent.insert(pos + k, clone)
            return
    changed = False
    for s in _segments(p):
        t = _seg_get(s)
        if "{{" not in t:
            continue

        def repl(m):
            flag, key = m.group(1), m.group(2).strip()
            if flag or key not in data:
                return m.group(0)
            v = data[key]
            if _is_image_value(v):
                images[prefix + key] = v
                return "{{" + prefix + key + "}}"
            return _to_str(v).replace("\n", " ")

        new = MARKER_RE.sub(repl, t)
        if new != t:
            _seg_set(s, new)
            changed = True
    if changed:
        mark_dirty(p)


def _is_image_value(v: Any) -> bool:
    return isinstance(v, (str, Path)) and str(v).lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif")) and Path(v).exists()


# ---------------- ⑤ 이미지 ----------------

def _load_image(path: str | Path, aspect: float | None) -> tuple[bytes, str, tuple[int, int]]:
    """이미지 로드 → (EXIF 회전 보정) → 목표 비율로 가운데 자르기 → JPEG/PNG 바이트."""
    im = Image.open(path)
    im = ImageOps.exif_transpose(im)
    if aspect:
        w, h = im.size
        if w / h > aspect:
            nw = int(h * aspect)
            im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
        else:
            nh = int(w / aspect)
            im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    if max(im.size) > 1600:
        im.thumbnail((1600, 1600))
    buf = io.BytesIO()
    if str(path).lower().endswith(".png") and im.mode in ("RGBA", "LA", "P"):
        im.save(buf, "PNG")
        ext = "png"
    else:
        im.convert("RGB").save(buf, "JPEG", quality=85)
        ext = "jpg"
    return buf.getvalue(), ext, im.size


def _fill_images(doc: HwpxDoc, root, images: dict, warnings: list) -> None:
    # (a) 그림 개체
    for pic in list(root.iter(f"{HP}pic")):
        sc = pic.find(f"{HP}shapeComment")
        if sc is None or not sc.text:
            continue
        m = MARKER_RE.search(sc.text)
        if not m:
            continue
        key = m.group(2).strip()
        src = images.get(key)
        if not src or not Path(src).exists():
            run = pic.getparent()
            run.remove(pic)
            continue
        cur = pic.find(f"{HP}curSz")
        aspect = int(cur.get("width")) / max(1, int(cur.get("height"))) if cur is not None else None
        data, ext, (pw, ph) = _load_image(src, aspect)
        item_id = doc.add_bindata(data, ext)
        pic.find(f"{HC}img").set("binaryItemIDRef", item_id)
        W, H = pw * HWPUNIT_PER_PX, ph * HWPUNIT_PER_PX
        org = pic.find(f"{HP}orgSz")
        if org is not None:
            org.set("width", str(W)); org.set("height", str(H))
        rect = pic.find(f"{HP}imgRect")
        if rect is not None:
            pts = rect.findall("*")
            for pt, (x, y) in zip(pts, [(0, 0), (W, 0), (W, H), (0, H)]):
                pt.set("x", str(x)); pt.set("y", str(y))
        clip = pic.find(f"{HP}imgClip")
        if clip is not None:
            clip.set("right", str(W)); clip.set("bottom", str(H))
        dim = pic.find(f"{HP}imgDim")
        if dim is not None:
            dim.set("dimwidth", str(W)); dim.set("dimheight", str(H))
        if cur is not None:
            sca = pic.find(f"{HP}renderingInfo/{HC}scaMatrix")
            if sca is not None:
                sca.set("e1", f"{int(cur.get('width')) / W:.6f}")
                sca.set("e5", f"{int(cur.get('height')) / H:.6f}")
        sc.text = f"그림입니다.\n원본 그림의 이름: {Path(src).name}"

    # (b) 배경그림 셀(사진 칸)
    for tc in list(root.iter(f"{HP}tc")):
        txt = "".join(para_text(p) for p in tc.iter(f"{HP}p"))
        m = MARKER_RE.search(txt)
        if not m or m.group(1):
            continue
        key = m.group(2).strip()
        bf = doc.border_fill(tc.get("borderFillIDRef"))
        has_img = bf is not None and bf.find(f".//{HC}imgBrush") is not None
        if key not in images and not has_img:
            continue
        for p in tc.iter(f"{HP}p"):
            if MARKER_RE.search(para_text(p)):
                set_para_text(p, MARKER_RE.sub("", para_text(p)))
        new_id, new_bf = doc.clone_border_fill(tc.get("borderFillIDRef"))
        tc.set("borderFillIDRef", new_id)
        brush = new_bf.find(f"{HC}fillBrush")
        src = images.get(key)
        if not src or not Path(src).exists():
            if brush is not None:
                new_bf.remove(brush)
            tc.set("_empty_slot", "1")
            continue
        sz = tc.find(f"{HP}cellSz")
        aspect = int(sz.get("width")) / max(1, int(sz.get("height"))) if sz is not None else None
        data, ext, _ = _load_image(src, aspect)
        item_id = doc.add_bindata(data, ext)
        if brush is None:
            brush = etree.SubElement(new_bf, f"{HC}fillBrush")
        for child in list(brush):
            brush.remove(child)
        ib = etree.SubElement(brush, f"{HC}imgBrush", mode="ZOOM")
        etree.SubElement(ib, f"{HC}img", binaryItemIDRef=item_id, bright="0", contrast="0", effect="REAL_PIC", alpha="0")

    # (c) 사진이 하나도 없는 사진 행은 삭제 (표 전체가 비면 표도 삭제)
    for tbl in list(root.iter(f"{HP}tbl")):
        trs = tbl.findall(f"{HP}tr")
        if not any(tc.get("_empty_slot") for tr in trs for tc in tr.findall(f"{HP}tc")):
            continue
        row_h = _row_height(trs[0])
        removed = 0
        for tr in trs:
            tcs = tr.findall(f"{HP}tc")
            if tcs and all(tc.get("_empty_slot") for tc in tcs):
                tbl.remove(tr)
                removed += 1
        for tc in tbl.iter(f"{HP}tc"):
            tc.attrib.pop("_empty_slot", None)
        if not tbl.findall(f"{HP}tr"):
            run = tbl.getparent()
            run.remove(tbl)
        else:
            _renumber_table(tbl, delta_rows=-removed, row_h=row_h)


def _prune_unused_bindata(doc: HwpxDoc) -> None:
    """어디에서도 참조하지 않는 BinData 제거(템플릿 자리표시 이미지 등)."""
    refs = set()
    for name in doc.section_names() + ["Contents/header.xml"]:
        refs |= set(re.findall(rb'binaryItemIDRef="([^"]+)"', doc.read(name)))
    for item_id, href in list(doc.bindata_items().items()):
        if href and href.startswith("BinData/") and item_id.encode() not in refs:
            doc.remove_bindata(item_id)


# ---------------- 진입점 ----------------

def fill(template_path: str | Path, data: dict, out_path: str | Path) -> FillResult:
    """OUT-01 양식에 값 채우기.

    data: {필드: str | list[dict](표/블록) | 이미지경로}
    반환: FillResult(remaining=[남은 마커], warnings=[...])
    """
    doc = HwpxDoc.load(template_path)
    warnings: list[str] = []
    images: dict[str, Any] = {k: v for k, v in data.items() if _is_image_value(v)}
    for root in doc.sections():
        normalize_markers(root)
        _fill_table_rows(root, data, images, warnings)
        _fill_blocks(root, data, images, warnings)
        for p in list(root.iter(f"{HP}p")):
            _substitute_para(p, data, images)
        _fill_images(doc, root, images, warnings)
    _prune_unused_bindata(doc)
    remaining, texts = [], []
    for root in doc.sections():
        for p in root.iter(f"{HP}p"):
            t = para_text(p)
            texts.append(t)
            remaining += [m.group(0) for m in MARKER_RE.finditer(t)]
    if "Preview/PrvText.txt" in doc.names():
        doc.write_entry("Preview/PrvText.txt", "\r\n".join(x for x in texts if x.strip())[:1024].encode("utf-8"))
    doc.save(out_path)
    return FillResult(remaining=remaining, warnings=warnings, out=str(out_path))
