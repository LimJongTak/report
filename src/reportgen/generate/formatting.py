"""표기 통일 (GEN-09). 금액은 천 단위 쉼표, 날짜는 '2026. 11. 12.(목)'."""
from __future__ import annotations

import datetime as dt
import re
from decimal import ROUND_HALF_UP, Decimal

WEEK = "월화수목금토일"


def parse_number(v) -> float | None:
    """'1,281,640원', '32명', 1281640 → 숫자. 실패 시 None"""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    m = re.search(r"-?\d[\d,]*(?:\.\d+)?", str(v))
    if not m:
        return None
    try:
        return float(m.group().replace(",", ""))
    except ValueError:
        return None


def round_half(x: float, nd: int = 0) -> float:
    q = Decimal(1).scaleb(-nd)
    return float(Decimal(str(x)).quantize(q, rounding=ROUND_HALF_UP))


def fmt_int(x) -> str:
    n = parse_number(x)
    return "" if n is None else f"{int(round_half(n)):,}"


def fmt_money(x, unit: str = "") -> str:
    s = fmt_int(x)
    return f"{s}{unit}" if s else ""


def fmt_pct(x: float | None, nd: int = 1) -> str:
    if x is None:
        return "-"
    v = round_half(x, nd)
    return f"{v:.{nd}f}%" if nd else f"{int(v)}%"


def ratio(actual, plan) -> float | None:
    """GEN-03 달성률(%) = 실적/계획×100 — 반드시 코드로 계산."""
    a, p = parse_number(actual), parse_number(plan)
    if a is None or p in (None, 0):
        return None
    return a / p * 100


def to_date(v) -> dt.date | None:
    if isinstance(v, dt.date):
        return v
    if not v:
        return None
    m = re.search(r"(20\d{2})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})", str(v))
    if not m:
        return None
    try:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def fmt_date(v, zero_pad: bool = True) -> str:
    """GEN-09 '2026. 07. 10.(금)'"""
    d = to_date(v)
    if not d:
        return str(v or "")
    mm = f"{d.month:02d}" if zero_pad else str(d.month)
    dd = f"{d.day:02d}" if zero_pad else str(d.day)
    return f"{d.year}. {mm}. {dd}.({WEEK[d.weekday()]})"


def fmt_date_range(start, end=None, time: str | None = None) -> str:
    s, e = to_date(start), to_date(end)
    if not s:
        return str(start or "")
    out = fmt_date(s)
    if e and e != s:
        if e.year == s.year:
            out += f" ~ {e.month:02d}. {e.day:02d}.({WEEK[e.weekday()]})"
        else:
            out += f" ~ {fmt_date(e)}"
    if time:
        out += f" {time}"
    return out


def normalize_text(s: str) -> str:
    """AI 문장 안의 날짜·금액 표기 정리(GEN-09)."""
    s = re.sub(r"(20\d{2})-(\d{2})-(\d{2})", lambda m: fmt_date(m.group(0)), s)
    s = re.sub(r"(?<![\d,.])(\d{5,})(?=\s?원)", lambda m: f"{int(m.group(1)):,}", s)
    return s
