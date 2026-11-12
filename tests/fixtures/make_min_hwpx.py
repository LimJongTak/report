"""테스트용 최소 HWPX 생성 (표 1개, 마커가 여러 run으로 쪼개진 문단 포함)."""
from __future__ import annotations

import zipfile
from pathlib import Path

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
NS = (f'xmlns:hp="{HP}" xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
      'xmlns:hc="http://www.hancom.co.kr/hwpml/2011/core" xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head"')


def _p(text_runs, pid="0", ppr="1"):
    runs = "".join(f'<hp:run charPrIDRef="{c}"><hp:t>{t}</hp:t></hp:run>' for c, t in text_runs)
    return f'<hp:p id="{pid}" paraPrIDRef="{ppr}" styleIDRef="0">{runs}<hp:linesegarray><hp:lineseg/></hp:linesegarray></hp:p>'


def _cell(r, c, text):
    return (f'<hp:tc borderFillIDRef="1"><hp:subList>{_p([("0", text)])}</hp:subList>'
            f'<hp:cellAddr colAddr="{c}" rowAddr="{r}"/><hp:cellSpan colSpan="1" rowSpan="1"/>'
            f'<hp:cellSz width="1000" height="500"/></hp:tc>')


def make(path: str | Path) -> Path:
    body = "".join([
        _p([("5", "제목: {{사"), ("6", "업명}} 보고")]),           # 쪼개진 마커
        _p([("0", "{{추진목적}}")], ppr="7"),                       # 여러 줄 문단
        '<hp:p id="0" paraPrIDRef="1" styleIDRef="0"><hp:run charPrIDRef="0"><hp:tbl rowCnt="2" colCnt="2">'
        '<hp:sz width="2000" height="1000"/>'
        f'<hp:tr>{_cell(0, 0, "항목")}{_cell(0, 1, "금액")}</hp:tr>'
        f'<hp:tr>{_cell(1, 0, "{{#예산}}{{항목}}")}{_cell(1, 1, "{{금액}}")}</hp:tr>'
        '</hp:tbl></hp:run></hp:p>',
        _p([("0", "{{#계획}}{{제목}}")]),
        _p([("0", "{{내용}}{{/계획}}")]),
        _p([("0", "합계 {{합계}}원")]),
    ])
    section = f'<?xml version="1.0" encoding="UTF-8"?><hs:sec {NS}>{body}</hs:sec>'
    header = f'<?xml version="1.0" encoding="UTF-8"?><hh:head {NS}><hh:refList><hh:borderFills itemCnt="1"><hh:borderFill id="1"/></hh:borderFills></hh:refList></hh:head>'
    hpf = ('<?xml version="1.0" encoding="UTF-8"?><opf:package xmlns:opf="http://www.idpf.org/2007/opf/">'
           '<opf:manifest><opf:item id="header" href="Contents/header.xml" media-type="application/xml"/>'
           '<opf:item id="section0" href="Contents/section0.xml" media-type="application/xml"/></opf:manifest></opf:package>')
    path = Path(path)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("Contents/content.hpf", hpf)            # 일부러 mimetype을 첫 항목이 아니게
        z.writestr("mimetype", "application/hwp+zip")
        z.writestr("Contents/header.xml", header)
        z.writestr("Contents/section0.xml", section)
    return path
