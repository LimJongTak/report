"""만족도 문항 막대그래프 PNG 생성 (수치는 코드 집계값 그대로)."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

_FONT_SET = False


def _font():
    global _FONT_SET
    if _FONT_SET:
        return
    for name in ("Malgun Gothic", "NanumGothic", "AppleGothic", "Noto Sans CJK KR"):
        if any(f.name == name for f in font_manager.fontManager.ttflist):
            plt.rcParams["font.family"] = name
            break
    plt.rcParams["axes.unicode_minus"] = False
    _FONT_SET = True


def likert_bar(item: dict, out: str | Path, size_px=(764, 434)) -> Path:
    """item: sheets.survey_item_view() 결과"""
    _font()
    labels = list(item["응답"].keys())
    counts = list(item["응답"].values())
    shares = list(item["비율"].values())
    dpi = 100
    fig, ax = plt.subplots(figsize=(size_px[0] / dpi, size_px[1] / dpi), dpi=dpi)
    colors = ["#2F4B8C", "#5A7BC0", "#A9B8D9", "#D9A5A5", "#B85C5C"]
    bars = ax.bar(labels, counts, color=colors, width=0.6)
    top = max(counts) if counts else 1
    for b, c, s in zip(bars, counts, shares):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + top * 0.02, f"{c}명 ({int(s)}%)",
                ha="center", va="bottom", fontsize=10)
    ax.set_ylim(0, top * 1.22 + 0.5)
    ax.set_title(item["문항"], fontsize=12, pad=10)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_yticks([])
    ax.tick_params(axis="x", labelsize=10)
    fig.tight_layout()
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=dpi)
    plt.close(fig)
    return out
