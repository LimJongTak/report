"""HWPX(OWPML) 읽기/쓰기 핵심 기능.

HWPX = ZIP + XML. 저장 시 규칙(CLAUDE.md 절대규칙 3):
- `mimetype`은 무압축(STORED) 첫 항목
- 나머지 항목 순서·압축방식 유지
- {{필드}}가 여러 run/t로 쪼개진 경우 첫 run의 charPrIDRef를 유지하며 병합
"""
from __future__ import annotations

import copy
import io
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree

NS = {
    "hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
    "hs": "http://www.hancom.co.kr/hwpml/2011/section",
    "hc": "http://www.hancom.co.kr/hwpml/2011/core",
    "hh": "http://www.hancom.co.kr/hwpml/2011/head",
    "opf": "http://www.idpf.org/2007/opf/",
}
HP = "{%s}" % NS["hp"]
HC = "{%s}" % NS["hc"]
HH = "{%s}" % NS["hh"]
OPF = "{%s}" % NS["opf"]

MARKER_RE = re.compile(r"\{\{\s*([#/]?)([^{}]+?)\s*\}\}")
HWPUNIT_PER_PX = 75  # 96dpi 기준 1px = 75 HWPUNIT


def q(tag: str) -> str:
    """'hp:p' → '{ns}p'"""
    pfx, local = tag.split(":")
    return "{%s}%s" % (NS[pfx], local)


@dataclass
class _Entry:
    name: str
    data: bytes
    compress_type: int


@dataclass
class HwpxDoc:
    """HWPX 문서 메모리 표현."""

    entries: list[_Entry] = field(default_factory=list)
    _xml: dict[str, etree._Element] = field(default_factory=dict)

    # ---------- 입출력 ----------
    @classmethod
    def load(cls, path: str | Path) -> "HwpxDoc":
        doc = cls()
        with zipfile.ZipFile(path) as z:
            for info in z.infolist():
                doc.entries.append(_Entry(info.filename, z.read(info.filename), info.compress_type))
        return doc

    def names(self) -> list[str]:
        return [e.name for e in self.entries]

    def read(self, name: str) -> bytes:
        if name in self._xml:
            return self._serialize(name)
        for e in self.entries:
            if e.name == name:
                return e.data
        raise KeyError(name)

    def xml(self, name: str) -> etree._Element:
        """XML 항목을 파싱해 캐시(수정 시 save 때 직렬화)."""
        if name not in self._xml:
            parser = etree.XMLParser(remove_blank_text=False, huge_tree=True)
            self._xml[name] = etree.fromstring(self.read(name), parser)
        return self._xml[name]

    def _serialize(self, name: str) -> bytes:
        return etree.tostring(self._xml[name], xml_declaration=True, encoding="UTF-8", standalone=True)

    def section_names(self) -> list[str]:
        secs = [n for n in self.names() if re.match(r"Contents/section\d+\.xml$", n)]
        return sorted(secs, key=lambda n: int(re.findall(r"\d+", n)[-1]))

    def sections(self) -> list[etree._Element]:
        return [self.xml(n) for n in self.section_names()]

    def header(self) -> etree._Element:
        return self.xml("Contents/header.xml")

    def write_entry(self, name: str, data: bytes, compress: int = zipfile.ZIP_DEFLATED) -> None:
        self._xml.pop(name, None)
        for e in self.entries:
            if e.name == name:
                e.data = data
                return
        self.entries.append(_Entry(name, data, compress))

    def remove_entry(self, name: str) -> None:
        self._xml.pop(name, None)
        self.entries = [e for e in self.entries if e.name != name]

    def save(self, path: str | Path) -> Path:
        """HWPX 저장. mimetype은 무압축 첫 항목으로."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        buf = io.BytesIO()
        ordered = sorted(self.entries, key=lambda e: 0 if e.name == "mimetype" else 1)
        with zipfile.ZipFile(buf, "w") as z:
            for e in ordered:
                data = self._serialize(e.name) if e.name in self._xml else e.data
                ct = zipfile.ZIP_STORED if e.name == "mimetype" else e.compress_type
                zi = zipfile.ZipInfo(e.name, date_time=(1980, 1, 1, 0, 0, 0))
                zi.compress_type = ct
                z.writestr(zi, data)
        path.write_bytes(buf.getvalue())
        return path

    # ---------- BinData ----------
    def _manifest(self) -> etree._Element:
        return self.xml("Contents/content.hpf").find(f"{OPF}manifest")

    def add_bindata(self, data: bytes, ext: str) -> str:
        """이미지를 BinData에 추가하고 manifest에 등록. 반환: item id"""
        ext = ext.lower().lstrip(".")
        ext = "jpg" if ext == "jpeg" else ext
        used = {it.get("id") for it in self._manifest()}
        n = 1
        while f"image{n}" in used or f"BinData/image{n}.{ext}" in self.names():
            n += 1
        item_id = f"image{n}"
        href = f"BinData/{item_id}.{ext}"
        self.write_entry(href, data, zipfile.ZIP_STORED)
        item = etree.SubElement(self._manifest(), f"{OPF}item")
        item.set("id", item_id)
        item.set("href", href)
        item.set("media-type", f"image/{ext}")
        item.set("isEmbeded", "1")
        return item_id

    def bindata_items(self) -> dict[str, str]:
        return {it.get("id"): it.get("href") for it in self._manifest()}

    def remove_bindata(self, item_id: str) -> None:
        man = self._manifest()
        for it in list(man):
            if it.get("id") == item_id:
                self.remove_entry(it.get("href"))
                man.remove(it)

    def replace_bindata(self, item_id: str, data: bytes, ext: str) -> None:
        """같은 item id를 유지한 채 이미지 내용 교체."""
        ext = ext.lower().lstrip(".")
        ext = "jpg" if ext == "jpeg" else ext
        for it in self._manifest():
            if it.get("id") == item_id:
                old = it.get("href")
                self.remove_entry(old)
                href = f"BinData/{item_id}.{ext}"
                self.write_entry(href, data, zipfile.ZIP_STORED)
                it.set("href", href)
                it.set("media-type", f"image/{ext}")
                return
        raise KeyError(item_id)

    # ---------- borderFill ----------
    def border_fill(self, bf_id: str) -> etree._Element | None:
        for bf in self.header().iter(f"{HH}borderFill"):
            if bf.get("id") == str(bf_id):
                return bf
        return None

    def clone_border_fill(self, bf_id: str) -> tuple[str, etree._Element]:
        """borderFill을 복제해 새 id로 등록."""
        src = self.border_fill(bf_id)
        parent = src.getparent()
        new_id = str(max(int(b.get("id")) for b in parent.findall(f"{HH}borderFill")) + 1)
        new = copy.deepcopy(src)
        new.set("id", new_id)
        parent.append(new)
        parent.set("itemCnt", str(len(parent.findall(f"{HH}borderFill"))))
        return new_id, new


# ---------- 텍스트 유틸 ----------

def _segments(p: etree._Element) -> list[tuple[etree._Element, str]]:
    """문단의 직속 run 아래 hp:t 텍스트 조각 목록. (요소, 'text'|'tail')"""
    segs = []
    for run in p.findall(f"{HP}run"):
        for t in run.findall(f"{HP}t"):
            segs.append((t, "text"))
            for child in t:
                segs.append((child, "tail"))
    return segs


def _seg_get(seg) -> str:
    el, attr = seg
    return (el.text if attr == "text" else el.tail) or ""


def _seg_set(seg, value: str) -> None:
    el, attr = seg
    if attr == "text":
        el.text = value
    else:
        el.tail = value


def para_text(p: etree._Element) -> str:
    """문단 직속 텍스트(중첩 표 제외)."""
    return "".join(_seg_get(s) for s in _segments(p))


def set_para_text(p: etree._Element, text: str) -> None:
    """문단 텍스트를 통째로 교체(첫 t에 몰아넣고 나머지 t는 비움)."""
    segs = _segments(p)
    if not segs:
        runs = p.findall(f"{HP}run")
        run = runs[0] if runs else etree.SubElement(p, f"{HP}run", charPrIDRef="0")
        t = etree.SubElement(run, f"{HP}t")
        t.text = text
    else:
        _seg_set(segs[0], text)
        for s in segs[1:]:
            _seg_set(s, "")
    mark_dirty(p)


def mark_dirty(p: etree._Element) -> None:
    """텍스트가 바뀐 문단의 줄배치 캐시(linesegarray) 제거 → 한컴이 다시 계산."""
    for ls in p.findall(f"{HP}linesegarray"):
        p.remove(ls)


def normalize_markers(root: etree._Element) -> int:
    """{{...}}가 여러 조각으로 쪼개진 경우 첫 조각으로 병합. 반환: 병합 수"""
    merged = 0
    for p in root.iter(f"{HP}p"):
        segs = _segments(p)
        if len(segs) < 2:
            continue
        texts = [_seg_get(s) for s in segs]
        full = "".join(texts)
        if "{{" not in full:
            continue
        # 글자 위치 → 조각 번호
        owner = [i for i, t in enumerate(texts) for _ in t]
        new_texts = [list(t) for t in texts]
        changed = False
        for m in MARKER_RE.finditer(full):
            a, b = m.start(), m.end() - 1
            sa, sb = owner[a], owner[b]
            if sa == sb:
                continue
            # 마커 글자를 모두 첫 조각(sa)으로 이동 → 첫 run의 글자모양 유지
            for pos in range(a, b + 1):
                owner[pos] = sa
            changed = True
            merged += 1
        if changed:
            buckets: list[list[str]] = [[] for _ in texts]
            for ch, i in zip(full, owner):
                buckets[i].append(ch)
            for s, chars in zip(segs, buckets):
                _seg_set(s, "".join(chars))
            del new_texts
    return merged


def find_markers(doc: HwpxDoc) -> list[dict]:
    """문서 내 모든 마커 목록 (LIB-02 기초 자료).

    반환 항목: {name, kind: field|table|block_start|block_end|image, in_cell, solo, row_fields}
    """
    out: list[dict] = []
    for root in doc.sections():
        normalize_markers(root)
        for p in root.iter(f"{HP}p"):
            txt = para_text(p)
            in_cell = _ancestor(p, f"{HP}tc") is not None
            for m in MARKER_RE.finditer(txt):
                flag, name = m.group(1), m.group(2).strip()
                kind = {"#": "repeat_start", "/": "block_end"}.get(flag, "field")
                out.append({
                    "name": name,
                    "kind": kind,
                    "in_cell": in_cell,
                    "solo": txt.strip() == m.group(0),
                })
        for pic in root.iter(f"{HP}pic"):
            sc = pic.find(f"{HP}shapeComment")
            if sc is not None and sc.text:
                for m in MARKER_RE.finditer(sc.text):
                    out.append({"name": m.group(2).strip(), "kind": "image", "in_cell": False, "solo": True})
    return out


def _ancestor(el: etree._Element, tag: str) -> etree._Element | None:
    cur = el.getparent()
    while cur is not None:
        if cur.tag == tag:
            return cur
        cur = cur.getparent()
    return None


ancestor = _ancestor
