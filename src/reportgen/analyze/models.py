"""계획·실적 구조화 데이터 모델 (GEN-01, GEN-02)."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Source(BaseModel):
    model_config = ConfigDict(extra="ignore")
    file: str = ""
    loc: str = ""
    quote: str = ""


class ScheduleRow(BaseModel):
    model_config = ConfigDict(extra="ignore")
    날짜: str = ""
    시간: str = ""
    내용: str = ""
    비고: str = ""


class BudgetRow(BaseModel):
    model_config = ConfigDict(extra="ignore")
    예산과목: str = ""
    세부항목: str = ""
    산출내역: str = ""
    금액: float | None = None


class SurveyItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    문항: str
    응답: dict[str, int] = Field(default_factory=dict)


class Survey(BaseModel):
    model_config = ConfigDict(extra="ignore")
    조사기간: str | None = None
    조사대상: str | None = None
    응답자수: int | None = None
    조사방법: str | None = None
    활용목적: str | None = None
    문항: list[SurveyItem] = Field(default_factory=list)


class Plan(BaseModel):
    """GEN-01 계획안 구조화"""
    model_config = ConfigDict(extra="allow")
    사업단명: str | None = None
    사업명: str | None = None
    행사명: str | None = None
    배경: list[str] = Field(default_factory=list)
    목적: list[str] = Field(default_factory=list)
    시작일: str | None = None
    종료일: str | None = None
    시간: str | None = None
    장소: str | None = None
    대상: str | None = None
    목표인원: float | None = None
    주요내용: list[str] = Field(default_factory=list)
    세부프로그램: list[ScheduleRow] = Field(default_factory=list)
    예산: list[BudgetRow] = Field(default_factory=list)
    재원: str | None = None
    기대효과: list[str] = Field(default_factory=list)
    만족도목표: float | None = None
    sources: dict[str, list[Source]] = Field(default_factory=dict)


class Actual(BaseModel):
    """GEN-02 결과 자료 구조화"""
    model_config = ConfigDict(extra="allow")
    행사명: str | None = None
    시작일: str | None = None
    종료일: str | None = None
    시간: str | None = None
    장소: str | None = None
    대상: str | None = None
    참여인원: float | None = None
    운영일정: list[ScheduleRow] = Field(default_factory=list)
    집행내역: list[BudgetRow] = Field(default_factory=list)
    재원: str | None = None
    성과: list[str] = Field(default_factory=list)
    특이사항: list[str] = Field(default_factory=list)
    만족도: Survey | None = None
    sources: dict[str, list[Source]] = Field(default_factory=dict)


def dump(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")
