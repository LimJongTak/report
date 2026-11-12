"""문체 프로필 생성 (LIB-07 / F-04).

1) 코드 통계: 어미 빈도, 기호 체계, 날짜·금액 표기, 장별 분량
2) (API 키가 있으면) Claude가 과거 보고서 전체를 분석해 서술형 프로필 작성
결과: library/style_profile.md
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from .. import config
from . import examples as ex

ENDINGS = {
    "~함/~임 (개조식)": r"(함|임|됨|음)\s*$",
    "~하였습니다/~되었습니다 (서술형)": r"(습니다|었습니다|였습니다)\.?\s*$",
    "명사형 종결(~제고, ~강화)": r"(제고|강화|확대|구축|향상|확보|마련|운영|도모|고취)\s*$",
    "~필요": r"필요\s*$",
}
SYMBOLS = ["○", "❍", "◦", "-", "※", "▸", "▶", "□", "■", "◎", "·"]


def profile_stats(texts: list[str]) -> dict:
    lines = [ln.strip() for t in texts for ln in t.splitlines() if ln.strip() and not ln.startswith(("#", "|", "- 형식"))]
    end_counts = {k: sum(1 for ln in lines if re.search(p, ln)) for k, p in ENDINGS.items()}
    sym = Counter()
    for ln in lines:
        for s in SYMBOLS:
            if ln.startswith(s):
                sym[s] += 1
    dates = Counter(re.findall(r"20\d{2}\.\s?\d{1,2}\.\s?\d{1,2}\.(?:\([월화수목금토일]\))?", "\n".join(lines)))
    date_style = "2026. 07. 10.(금)" if any(re.search(r"\.\s0\d\.", d) for d in dates) else "2026. 7. 10.(금)"
    money = len(re.findall(r"\d{1,3}(?:,\d{3})+원?", "\n".join(lines)))
    avg_len = sum(len(ln) for ln in lines) / max(1, len(lines))
    return {"lines": len(lines), "endings": end_counts, "symbols": dict(sym.most_common()),
            "date_examples": [d for d, _ in dates.most_common(5)], "date_style": date_style,
            "money_mentions": money, "avg_line_chars": round(avg_len, 1)}


def build(use_ai: bool = True, log_dir: Path | None = None) -> Path:
    """LIB-07 style_profile.md 생성."""
    exs = [e for e in ex.list_examples() if e.get("추출상태") == "정상"]
    texts = [ex.load_text(e["id"]) for e in exs]
    st = profile_stats(texts)
    out = config.path("library") / "style_profile.md"
    stats_md = [
        "## 1. 코드 통계 (자동 계산)",
        f"- 분석 사례: {len(exs)}건 ({', '.join(e['사업명'] for e in exs)})",
        f"- 분석 줄 수: {st['lines']}, 줄당 평균 {st['avg_line_chars']}자",
        "- 문장 끝 유형: " + ", ".join(f"{k} {v}회" for k, v in st["endings"].items()),
        "- 줄머리 기호: " + (", ".join(f"'{k}' {v}회" for k, v in st["symbols"].items()) or "없음(문단 글머리 자동번호 사용)"),
        f"- 날짜 표기 예: {', '.join(st['date_examples']) or '-'} → 표준: {st['date_style']}",
        f"- 금액 표기: 천 단위 쉼표 사용({st['money_mentions']}회), 표 안에서는 '원' 생략",
    ]
    body = ""
    if use_ai and config.has_api_key() and texts:
        from .. import llm
        joined = "\n\n".join(f"=== 사례: {e['사업명']} ({e.get('사업유형')}) ===\n{t[:12000]}" for e, t in zip(exs, texts))
        body, _ = llm.call_text("style_profile", {"examples": joined, "stats": "\n".join(stats_md)}, log_dir=log_dir)
    else:
        seed = config.path("library") / "style_profile_seed.md"
        body = seed.read_text(encoding="utf-8") if seed.exists() else ""
    out.write_text("# 문체 프로필 (결과보고)\n\n" + "\n".join(stats_md) + "\n\n" + body.strip() + "\n", encoding="utf-8")
    return out


def load() -> str:
    p = config.path("library") / "style_profile.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""
