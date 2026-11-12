# ReportGen — Claude Code 프로젝트 규칙

## 프로젝트 요약
결과보고 양식(.hwpx)과 과거 결과보고를 라이브러리로 등록해 두고, 새 건의 계획안과 결과 자료를 넣으면
양식에 맞는 결과보고서(.hwpx + PDF)를 자동 생성하는 로컬 Streamlit 앱.

## 반드시 먼저 읽을 문서
- docs/01_과업지시서.md — 목적, 범위, 검수 기준
- docs/02_요구사항명세서.md — 요구사항 ID (LIB/PRJ/ING/GEN/VAL/OUT/NFR)
- docs/03_기능정의서.md — 구조, 폴더, 데이터 형식, 핵심 로직 규칙
- docs/04_프롬프트북.md — 개발 단계 순서

## 개발 규칙
- 언어: Python 3.11+, 가상환경 `.venv`. 패키지 추가 시 requirements.txt에 버전 고정.
- 코드는 `src/reportgen/`에, AI 프롬프트 문구는 `prompts/*.md`에 분리. UI(app.py, ui/)에는 비즈니스 로직 금지.
- 설정값(모델명, 토큰, 경로)은 `config/settings.yaml`, 비밀값은 `.env`. 하드코딩 금지.
- 커밋 메시지와 주석, 사용자 안내 문구는 한국어.
- 새 기능에는 pytest 테스트를 추가하고, 작업 끝에 전체 테스트를 돌린다.
- 구현한 요구사항 ID를 함수 docstring에 적는다. 예: `"""GEN-03 계획대비실적 계산"""`

## 절대 규칙
1. **숫자는 코드가 계산한다.** 달성률·합계·집행률을 AI에게 계산시키지 않는다.
2. **근거 없는 사실 금지.** 자료에 없는 내용은 `[확인 필요: 사유]`로 남긴다. 모든 초안 필드에 sources를 기록한다.
3. **HWPX 무결성.** 저장 시 `mimetype`은 무압축 첫 항목. 치환 전 run 정규화, XML 이스케이프, 원래 charPrIDRef/paraPrIDRef 유지.
4. **원본 보호.** library와 input의 원본 파일은 수정하지 않는다. 결과는 output/, 중간물은 work/.
5. **개인정보.** AI 전송 전 마스킹(기본 ON). `.env`, `projects/`는 Git에 올리지 않는다.

## 자주 쓰는 명령
```
.venv\Scripts\activate
streamlit run app.py
pytest -q
python scripts/import_library.py --templates <경로> --examples <경로>
python scripts/backtest.py
```

## 사용자 정보
- 사용자는 비개발자 관점에서 결과를 확인한다. 완료 시 "무엇을 만들었는지 / 어떻게 확인하는지"를 짧게 안내할 것.
- 한컴오피스에서 직접 열어 확인해야 하는 단계는 확인을 요청하고 결과를 기다릴 것.
