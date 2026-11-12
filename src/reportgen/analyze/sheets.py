"""표 자료에서 숫자 사실을 코드로 뽑아내기 (GEN-02 보조, 절대규칙 1).

- 만족도 설문(원자료/집계표) → 문항별 응답 수, 긍정률
- 참석자 명단 → 인원 수
- 지출내역 → 집행 항목·금액·합계
AI가 숫자를 세거나 더하지 않도록, 표로 들어온 자료는 여기서 계산한다.
"""
from __future__ import annotations

import re

from ..generate.formatting import parse_number, round_half
from ..ingest.base import ExtractedDoc

LIKERT = ["매우 그렇다", "그렇다", "보통이다", "그렇지 않다", "매우 그렇지 않다"]
_LIKERT_ALIASES = {
    "매우그렇다": 0, "매우만족": 0, "매우 만족": 0, "5": 0,
    "그렇다": 1, "만족": 1, "4": 1,
    "보통이다": 2, "보통": 2, "3": 2,
    "그렇지않다": 3, "그렇지 않다": 3, "불만족": 3, "2": 3,
    "매우그렇지않다": 4, "매우 그렇지 않다": 4, "매우불만족": 4, "매우 불만족": 4, "1": 4,
}


def likert_index(v: str) -> int | None:
    s = re.sub(r"\s+", "", str(v or ""))
    s = re.sub(r"^\d\)|^\(\d\)|\(\d\)$", "", s)
    if s in _LIKERT_ALIASES:
        return _LIKERT_ALIASES[s]
    m = re.fullmatch(r"([1-5])(?:\.0)?(?:점)?", s)
    return _LIKERT_ALIASES.get(m.group(1)) if m else None


def _src(doc: ExtractedDoc, loc: str) -> dict:
    return {"file": doc.file, "loc": loc, "quote": "코드 집계"}


# ---------------- 만족도 ----------------

def _survey_raw(rows: list[list[str]]):
    """원자료형: 행=응답자, 열=문항. 문항 열 = 값의 80% 이상이 리커트 척도."""
    head, body = rows[0], rows[1:]
    if len(body) < 3:
        return None
    items = []
    for c, h in enumerate(head):
        vals = [r[c] for r in body if c < len(r) and str(r[c]).strip()]
        if len(vals) < max(3, len(body) * 0.5):
            continue
        idx = [likert_index(v) for v in vals]
        hits = sum(i is not None for i in idx)
        textual = sum(1 for v in vals if not re.fullmatch(r"\s*\d+(\.0)?\s*", str(v)))
        numeric_ok = len(h.strip()) >= 6  # 숫자 1~5 척도는 머리글이 질문형일 때만 인정
        if hits >= 0.8 * len(vals) and (textual or numeric_ok):
            counts = [0] * 5
            for i in idx:
                if i is not None:
                    counts[i] += 1
            items.append({"문항": h.strip(), "counts": counts})
    if not items:
        return None
    respondents = sum(1 for r in body if any(str(x).strip() for x in r))
    return items, respondents


def _survey_agg(rows: list[list[str]]):
    """집계형: 머리행에 리커트 단계, 각 행=문항, 셀=응답 수."""
    head = [re.sub(r"\s+", "", h) for h in rows[0]]
    cols = {}
    for c, h in enumerate(head):
        i = _LIKERT_ALIASES.get(h)
        if i is not None and not h.isdigit():
            cols[i] = c
    if len(cols) < 3:
        return None
    items = []
    for r in rows[1:]:
        name = next((x for x in r if x and parse_number(x) is None), "")
        counts = [int(parse_number(r[cols[i]]) or 0) if i in cols and cols[i] < len(r) else 0 for i in range(5)]
        if name and sum(counts):
            items.append({"문항": name.strip(), "counts": counts})
    if not items:
        return None
    return items, max(sum(it["counts"]) for it in items)


def survey_item_view(name: str, counts: list[int]) -> dict:
    """문항 하나의 표시용 수치(모두 코드 계산)."""
    n = sum(counts)
    share = [round_half(c / n * 100) if n else 0 for c in counts]
    pos = counts[0] + counts[1]
    pos_rate = round_half(pos / n * 100) if n else 0
    return {
        "문항": name,
        "응답": dict(zip(LIKERT, counts)),
        "응답자수": n,
        "비율": dict(zip(LIKERT, share)),
        "긍정수": pos,
        "긍정률": pos_rate,
        "응답분포": ", ".join(f"{k}: {v}" for k, v in zip(LIKERT, counts)),
        "요약수치": ", ".join(f"{k} {int(s)}%({c}명)" for k, c, s in zip(LIKERT, counts, share) if c) + f" / 긍정 {int(pos_rate)}%({pos}명)",
    }


def detect_survey(docs: list[ExtractedDoc]) -> dict | None:
    for d in docs:
        for b in d.blocks:
            if b.kind != "table" or not b.rows or len(b.rows) < 2:
                continue
            res = _survey_agg(b.rows) or _survey_raw(b.rows)
            if res:
                items, n = res
                return {
                    "items": [survey_item_view(it["문항"], it["counts"]) for it in items],
                    "응답자수": n,
                    "sources": [_src(d, b.loc)],
                    "method": "코드 집계",
                }
    return None


# ---------------- 명단 ----------------
NAME_HEAD = re.compile(r"^(이름|성명|성 명|참가자|참석자|학생명|수강생)$")
ATTEND_HEAD = re.compile(r"(출석|참석|이수|수료)")
YES = {"o", "○", "◯", "y", "yes", "1", "출석", "참석", "이수", "수료", "참여", "v", "√", "✓"}


def detect_roster(docs: list[ExtractedDoc]) -> dict | None:
    best = None
    for d in docs:
        for b in d.blocks:
            if b.kind != "table" or not b.rows or len(b.rows) < 2:
                continue
            head = [h.strip() for h in b.rows[0]]
            ncol = next((i for i, h in enumerate(head) if NAME_HEAD.match(h.replace(" ", ""))), None)
            if ncol is None:
                continue
            names = [r for r in b.rows[1:] if ncol < len(r) and re.fullmatch(r"[가-힣A-Za-z\s*○●]{2,20}", r[ncol].strip() or "-")]
            acol = next((i for i, h in enumerate(head) if ATTEND_HEAD.search(h)), None)
            res = {"명단인원": len(names), "sources": [_src(d, b.loc)], "file": d.file}
            if acol is not None:
                res["참석인원"] = sum(1 for r in names if acol < len(r) and r[acol].strip().lower() in YES)
                res["참석열"] = head[acol]
            if not best or res["명단인원"] > best["명단인원"]:
                best = res
    return best


# ---------------- 지출 ----------------
AMOUNT_HEAD = re.compile(r"(집행액|집행금액|지출액|사용액|금액|합계액)")
COLS = {
    "예산과목": re.compile(r"(예산과목|비목|과목|예산항목)"),
    "세부항목": re.compile(r"(세부항목|세목|세부과목|세부)"),
    "산출내역": re.compile(r"(산출내역|산출근거|내역|적요|내용|품목|사용처|항목)"),
}
TOTAL_ROW = re.compile(r"^(합\s*계|총\s*계|소\s*계|계)$")


def detect_budget(docs: list[ExtractedDoc], prefer: str = "집행") -> dict | None:
    """지출(집행) 내역 표 → rows, 합계(코드 계산). 표에 적힌 합계와 다르면 경고."""
    cands = []
    for d in docs:
        for b in d.blocks:
            if b.kind != "table" or not b.rows or len(b.rows) < 2:
                continue
            head = [h.replace(" ", "") for h in b.rows[0]]
            acols = [i for i, h in enumerate(head) if AMOUNT_HEAD.search(h)]
            if not acols:
                continue
            ac = next((i for i in acols if "집행" in head[i] or "지출" in head[i]), acols[-1])
            cmap = {}
            for k, pat in COLS.items():
                cmap[k] = next((i for i, h in enumerate(head) if pat.search(h) and i != ac and i not in cmap.values()), None)
            rows, stated_total = [], None
            for r in b.rows[1:]:
                amt = parse_number(r[ac]) if ac < len(r) else None
                label = " ".join(x for x in r if x and parse_number(x) is None).strip()
                if TOTAL_ROW.match(label.replace(" ", "")) or any(TOTAL_ROW.match((x or "").replace(" ", "")) for x in r):
                    stated_total = amt
                    continue
                if amt is None:
                    continue
                row = {k: (r[i].strip() if i is not None and i < len(r) else "") for k, i in cmap.items()}
                row["금액"] = amt
                rows.append(row)
            if rows:
                total = sum(x["금액"] for x in rows)
                score = (prefer in head[ac]) * 2 + len(rows)
                cands.append((score, {"rows": rows, "합계": total, "표기합계": stated_total,
                                      "합계일치": stated_total is None or abs(stated_total - total) < 1,
                                      "sources": [_src(d, b.loc)], "금액열": b.rows[0][ac]}))
    if not cands:
        return None
    cands.sort(key=lambda x: -x[0])
    return cands[0][1]


# ---------------- 일정 ----------------
SCHED_COLS = {"날짜": re.compile(r"(날짜|일자|일시|요일)"), "시간": re.compile(r"(시간|교시)"),
              "내용": re.compile(r"(내용|프로그램|일정|세부|주제)"), "비고": re.compile(r"(비고|장소|강사)")}


def detect_schedule(docs: list[ExtractedDoc]) -> dict | None:
    """머리행에 시간·내용 열이 있는 표 → 운영일정 rows (옮겨 적기만 함)."""
    for d in docs:
        for b in d.blocks:
            if b.kind != "table" or not b.rows or len(b.rows) < 2:
                continue
            head = [h.replace(" ", "") for h in b.rows[0]]
            cmap = {}
            for k, pat in SCHED_COLS.items():
                cmap[k] = next((i for i, h in enumerate(head) if pat.search(h) and i not in cmap.values()), None)
            if cmap["시간"] is None or cmap["내용"] is None or any(AMOUNT_HEAD.search(h) for h in head):
                continue
            rows = [{k: (r[i].strip() if i is not None and i < len(r) else "") for k, i in cmap.items()} for r in b.rows[1:]]
            rows = [r for r in rows if r["내용"] or r["시간"]]
            if rows:
                return {"rows": rows, "sources": [_src(d, b.loc) | {"quote": "표 옮김"}]}
    return None
