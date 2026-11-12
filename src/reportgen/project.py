"""프로젝트(건) 관리 (PRJ-01~03 / F-06).

projects/<YYYYMMDD_사업명>/
  project.yaml
  input/plan/  input/materials/
  work/extracted/  work/logs/  plan.json actual.json comparison.json draft.json validation.json
  output/
"""
from __future__ import annotations

import datetime as dt
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from . import config


def _safe(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|\s]+', "_", name.strip())[:60]


@dataclass
class Project:
    dir: Path

    # ---- 경로 ----
    @property
    def plan_dir(self) -> Path:
        return self.dir / "input" / "plan"

    @property
    def materials_dir(self) -> Path:
        return self.dir / "input" / "materials"

    @property
    def work(self) -> Path:
        return self.dir / "work"

    @property
    def extracted_dir(self) -> Path:
        return self.work / "extracted"

    @property
    def logs_dir(self) -> Path:
        return self.work / "logs"

    @property
    def output_dir(self) -> Path:
        return self.dir / "output"

    @property
    def id(self) -> str:
        return self.dir.name

    # ---- 메타 ----
    @property
    def meta(self) -> dict:
        p = self.dir / "project.yaml"
        return yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else {}

    def update_meta(self, **kw) -> None:
        m = self.meta
        m.update(kw)
        (self.dir / "project.yaml").write_text(yaml.safe_dump(m, allow_unicode=True, sort_keys=False), encoding="utf-8")

    # ---- 작업 파일 ----
    def read_json(self, name: str, default: Any = None) -> Any:
        p = self.work / name
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default

    def write_json(self, name: str, data: Any) -> Path:
        p = self.work / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        return p

    def add_file(self, src: str | Path | bytes, filename: str, role: str = "materials") -> Path:
        """ING-01 계획안(plan) 또는 자료(materials) 추가. 원본은 복사만 한다."""
        d = self.plan_dir if role == "plan" else self.materials_dir
        d.mkdir(parents=True, exist_ok=True)
        dst = d / Path(filename).name
        if isinstance(src, bytes):
            dst.write_bytes(src)
        else:
            shutil.copy2(src, dst)
        return dst

    def remove_file(self, filename: str, role: str = "materials") -> None:
        d = self.plan_dir if role == "plan" else self.materials_dir
        (d / filename).unlink(missing_ok=True)
        for ext in (".md", ".json"):
            (self.extracted_dir / f"{filename}{ext}").unlink(missing_ok=True)

    def files(self, role: str) -> list[Path]:
        d = self.plan_dir if role == "plan" else self.materials_dir
        return sorted(p for p in d.glob("*") if p.is_file()) if d.exists() else []

    def photos(self) -> list[Path]:
        from .ingest import IMAGE_EXT
        return [p for p in self.files("materials") if p.suffix.lower() in IMAGE_EXT]

    def output_basename(self) -> str:
        """OUT-05 YYYYMMDD_사업명_결과보고"""
        m = self.meta
        date = (m.get("date") or dt.date.today().isoformat()).replace("-", "")
        return config.get("output.filename", "{date}_{name}_결과보고").format(date=date, name=_safe(m.get("name", "사업")))


def projects_dir() -> Path:
    return config.path("projects")


def create(name: str, template_id: str, date: str | None = None) -> Project:
    """PRJ-01/02 새 프로젝트 생성."""
    date = date or dt.date.today().isoformat()
    base = f"{date.replace('-', '')}_{_safe(name)}"
    d = projects_dir() / base
    n = 2
    while d.exists():
        d = projects_dir() / f"{base}_{n}"
        n += 1
    p = Project(d)
    for sub in (p.plan_dir, p.materials_dir, p.extracted_dir, p.logs_dir, p.output_dir):
        sub.mkdir(parents=True, exist_ok=True)
    p.update_meta(name=name, template_id=template_id, date=date,
                  created=dt.datetime.now().isoformat(timespec="seconds"), mask=bool(config.get("privacy.mask_default", True)))
    return p


def open_project(project_id: str) -> Project:
    """PRJ-03 기존 프로젝트 열기."""
    d = projects_dir() / project_id
    if not (d / "project.yaml").exists():
        raise FileNotFoundError(project_id)
    return Project(d)


def list_projects() -> list[dict]:
    out = []
    for y in sorted(projects_dir().glob("*/project.yaml"), reverse=True):
        m = yaml.safe_load(y.read_text(encoding="utf-8")) or {}
        m["id"] = y.parent.name
        out.append(m)
    return out
