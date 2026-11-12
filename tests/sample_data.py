"""테스트·시연용 가상 자료 생성 (실제 인물·기관 정보 아님)."""
from __future__ import annotations

import random
from pathlib import Path

import docx
from openpyxl import Workbook
from PIL import Image, ImageDraw

NAMES = ["김하늘", "이도윤", "박서준", "최지우", "정민재", "강예린", "조하준", "윤서아", "장태윤", "임가온",
         "한지호", "오세린", "서준혁", "신유나", "권도현", "황보람", "안지민", "송다인", "류시우", "전하린",
         "홍길순", "문채원", "양승우", "배수아"]


def make(folder: str | Path) -> dict:
    folder = Path(folder)
    plan_dir, mat_dir = folder / "plan", folder / "materials"
    plan_dir.mkdir(parents=True, exist_ok=True)
    mat_dir.mkdir(parents=True, exist_ok=True)

    d = docx.Document()
    d.add_heading("2026 클라우드 실무 기업 현장견학 운영 계획(안)", 1)
    for line in [
        "1. 사업단: AI인재양성부트캠프 사업",
        "2. 추진배경: 전공 교육에서 익힌 클라우드 기술이 실제 기업 현장에서 어떻게 쓰이는지 경험할 기회 필요",
        "3. 추진목적: 기업 데이터센터 견학과 현직자 멘토링으로 실무 이해도 제고 및 진로 설계 지원",
        "4. 일시: 2026. 11. 5.(목) 08:30 ~ 19:00",
        "5. 장소: 가나클라우드 판교 데이터센터",
        "6. 대상: 부트캠프 수료생 및 참여교수 (목표 25명)",
        "7. 재원: AI인재양성부트캠프 사업비",
        "8. 만족도 목표: 긍정 응답 90% 이상",
    ]:
        d.add_paragraph(line)
    t = d.add_table(rows=1, cols=4)
    for c, h in zip(t.rows[0].cells, ["날짜", "시간", "내용", "비고"]):
        c.text = h
    for row in [("5일(목)", "08:30", "학교 출발", "정문 집결"), ("5일(목)", "11:00", "데이터센터 견학", ""),
                ("5일(목)", "13:00", "중식", ""), ("5일(목)", "14:00~15:30", "현직자 멘토링", "세미나실"),
                ("5일(목)", "19:00", "학교 도착", "")]:
        cells = t.add_row().cells
        for c, v in zip(cells, row):
            c.text = v
    t2 = d.add_table(rows=1, cols=4)
    for c, h in zip(t2.rows[0].cells, ["예산과목", "세부항목", "산출내역", "금액"]):
        c.text = h
    for row in [("연구활동비", "비교과교육과정운영비", "버스 임차(1대)", "900,000"),
                ("연구활동비", "비교과교육과정운영비", "식대 25명×12,000원", "300,000"),
                ("연구활동비", "비교과교육과정운영비", "여행자보험 25명", "75,000")]:
        cells = t2.add_row().cells
        for c, v in zip(cells, row):
            c.text = v
    d.save(plan_dir / "현장견학_운영계획.docx")

    wb = Workbook()
    ws = wb.active
    ws.title = "명단"
    ws.append(["번호", "성명", "학과", "연락처", "출석"])
    for i, n in enumerate(NAMES[:23], 1):
        ws.append([i, n, "컴퓨터공학과", f"010-{1000 + i:04d}-{2000 + i:04d}", "O" if i <= 22 else ""])
    wb.save(mat_dir / "참석자명단.xlsx")

    wb = Workbook()
    ws = wb.active
    ws.title = "지출"
    ws.append(["예산과목", "세부항목", "산출내역", "집행액", "비고"])
    ws.append(["연구활동비", "비교과교육과정운영비", "버스 임차(1대)", 880000, ""])
    ws.append(["연구활동비", "비교과교육과정운영비", "중식 22명", 264000, ""])
    ws.append(["연구활동비", "비교과교육과정운영비", "여행자보험 22명", 66000, ""])
    ws.append(["합계", "", "", 1210000, ""])
    wb.save(mat_dir / "지출내역.xlsx")

    rnd = random.Random(7)
    qs = ["클라우드 분야 이해도 향상", "프로그램 구성 유익성", "진로 설정 동기부여", "전반적 만족도"]
    scale = ["매우 그렇다", "그렇다", "보통이다", "그렇지 않다", "매우 그렇지 않다"]
    wb = Workbook()
    ws = wb.active
    ws.title = "응답"
    ws.append(["타임스탬프"] + qs + ["기타 의견"])
    for i in range(20):
        ws.append([f"2026-11-0{6 + i % 3} 10:{i:02d}"] + [rnd.choices(scale, [14, 5, 1, 0, 0])[0] for _ in qs] + [""])
    wb.save(mat_dir / "만족도조사_응답.xlsx")

    (mat_dir / "운영메모.txt").write_text(
        "2026. 11. 5.(목) 가나클라우드 판교 데이터센터 현장견학 실시.\n"
        "참석: 수료생 및 교수 22명. 데이터센터 서버룸·관제센터 견학, 현직 엔지니어 3명과 멘토링 진행.\n"
        "만족도 조사: 2026. 11. 6. ~ 11. 8. 온라인 설문, 20명 응답.\n"
        "학생 의견: 실제 운영 환경을 보며 클라우드 직무를 구체적으로 이해했다는 반응이 많았음.\n",
        encoding="utf-8")

    for i, color in enumerate([(70, 110, 170), (90, 150, 120), (160, 120, 80), (120, 90, 150)], 1):
        im = Image.new("RGB", (1600, 1200), color)
        ImageDraw.Draw(im).text((60, 60), f"SAMPLE PHOTO {i}", fill=(255, 255, 255))
        im.save(mat_dir / f"사진{i}.jpg", quality=80)
    return {"plan": plan_dir, "materials": mat_dir}
