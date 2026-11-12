"""개인정보 마스킹 (NFR-02, F-16).

AI로 보내기 전에 이름·전화번호·이메일·학번을 토큰([이름1] 등)으로 바꾸고,
치환표는 프로젝트 work/ 폴더에만 저장한다. 초안을 받으면 원래 값으로 되돌린다.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

PHONE = re.compile(r"(?<!\d)01[016789][-.\s]?\d{3,4}[-.\s]?\d{4}(?!\d)")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
STUDENT_ID = re.compile(r"(?<!\d)(?:19|20)\d{6,8}(?!\d)")
NAME_HEADERS = ("이름", "성명", "학생명", "참가자", "수상자", "담당자", "강사", "성 명")


class Masker:
    def __init__(self, table_path: str | Path | None = None):
        self.table_path = Path(table_path) if table_path else None
        self.forward: dict[str, str] = {}
        if self.table_path and self.table_path.exists():
            self.forward = json.loads(self.table_path.read_text(encoding="utf-8"))

    def _token(self, kind: str, value: str) -> str:
        if value not in self.forward:
            n = sum(1 for t in self.forward.values() if t.startswith(f"[{kind}")) + 1
            self.forward[value] = f"[{kind}{n}]"
        return self.forward[value]

    def learn_names_from_rows(self, rows: list[list[str]]) -> None:
        """표 머리행에 '이름/성명' 열이 있으면 그 열 값을 이름으로 학습."""
        if not rows:
            return
        head = [c.replace(" ", "") for c in rows[0]]
        cols = [i for i, h in enumerate(head) if any(h.startswith(k.replace(" ", "")) for k in NAME_HEADERS)]
        for r in rows[1:]:
            for i in cols:
                if i < len(r):
                    v = r[i].strip()
                    if 2 <= len(v) <= 4 and re.fullmatch(r"[가-힣]+", v):
                        self._token("이름", v)

    def mask(self, text: str) -> str:
        text = EMAIL.sub(lambda m: self._token("이메일", m.group()), text)
        text = PHONE.sub(lambda m: self._token("전화", m.group()), text)
        text = STUDENT_ID.sub(lambda m: self._token("학번", m.group()), text)
        for value, tok in sorted(self.forward.items(), key=lambda kv: -len(kv[0])):
            if tok.startswith("[이름"):
                text = text.replace(value, tok)
        return text

    def unmask(self, text: str) -> str:
        for value, tok in self.forward.items():
            text = text.replace(tok, value)
        return text

    def unmask_obj(self, obj):
        if isinstance(obj, str):
            return self.unmask(obj)
        if isinstance(obj, list):
            return [self.unmask_obj(x) for x in obj]
        if isinstance(obj, dict):
            return {k: self.unmask_obj(v) for k, v in obj.items()}
        return obj

    def save(self) -> None:
        if self.table_path:
            self.table_path.parent.mkdir(parents=True, exist_ok=True)
            self.table_path.write_text(json.dumps(self.forward, ensure_ascii=False, indent=1), encoding="utf-8")


class NoMasker(Masker):
    def mask(self, text: str) -> str:
        return text

    def unmask(self, text: str) -> str:
        return text
