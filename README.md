# ReportGen — 결과보고 자동생성 프로그램

결과보고 양식(.hwpx)과 과거 결과보고서를 라이브러리로 등록해 두고, 새 행사의 **계획안 + 결과 자료**를 넣으면
양식에 맞는 **결과보고서(.hwpx + PDF)** 와 **근거보고서(.md)** 를 만듭니다.

- 숫자(인원·합계·달성률·만족도 비율)는 **프로그램이 계산**하고, AI는 문장만 씁니다.
- 자료에 없는 내용은 지어내지 않고 `[확인 필요: 사유]`로 남깁니다.
- 모든 파일은 이 PC에만 저장되며, AI로 보내기 전 이름·전화·이메일·학번을 가립니다(기본 켜짐).

## 1. 설치·실행

1. (처음 한 번) `.env.example`을 `.env`로 복사하고 `ANTHROPIC_API_KEY=` 뒤에 API 키를 붙여 넣습니다.
   - 키가 없어도 실행됩니다. 이때는 자료·숫자 항목(일정표, 예산표, 인원, 만족도 집계·그래프, 사진)만 자동으로 채워지고
     문장 항목은 `[확인 필요: AI 미연결]`로 표시됩니다.
2. **`run.bat` 더블클릭** → 브라우저에 `http://localhost:8501` 화면이 열립니다.

개발자용 명령:
```
.venv\Scripts\activate
streamlit run app.py
pytest -q
python scripts/import_library.py --templates <경로> --examples <경로> [--plans <경로>]
python scripts/import_library.py --build-default <과거보고서.hwp|hwpx>
python scripts/backtest.py
python scripts/diagnose.py
```

## 2. 사용 순서

| 화면 | 할 일 |
|---|---|
| 1. 라이브러리 | 양식·과거 사례 확인, schema(필드 정의) 수정, 문체 프로필 다시 생성 |
| 2. 새 결과보고 | 프로젝트 만들기 → 계획안·결과 자료 올리기 → **1) 추출 → 2) 구조화 → 3) 초안 생성** |
| 3. 검토 | 필드별 초안 / 근거 / 원문을 나란히 보고 수정·확정, 필요하면 "더 짧게" 같은 지시로 재생성 |
| 4. 출력 | 사진 고르기 → **HWPX 생성** (+PDF) → 근거보고서 확인 |

올리면 좋은 결과 자료
- 참석자 명단(.xlsx, '성명' 열 + '출석' 열) → 참여인원 자동 계산
- 지출내역(.xlsx, '집행액' 또는 '금액' 열) → 예산표·합계 자동, 적힌 합계와 다르면 경고
- 만족도 설문 응답(.xlsx, 구글폼 내보내기 형태 / 또는 문항별 집계표) → 문항별 비율·그래프 자동
- 운영 메모(.txt/.docx), 행사 사진(.jpg)

## 3. 양식 마킹 방법 (새 양식 추가)

한글에서 기존 결과보고 양식을 열고 채울 자리에 아래처럼 적은 뒤 **.hwpx로 저장**해서 라이브러리에 등록합니다.

| 표시 | 의미 |
|---|---|
| `{{사업명}}` | 글자 치환. 문단에 이것만 있으면 여러 줄 값이 같은 문단 모양으로 여러 문단이 됨 |
| 표의 반복할 행 첫 칸에 `{{#예산집행내역}}{{예산과목}}`, 나머지 칸 `{{금액}}` 등 | 데이터 행 수만큼 행 복제 |
| 문단 `{{#향후계획}}{{제목}}` … `{{내용}}{{/향후계획}}` | 문단 묶음 반복 |
| 그림의 [개체 속성 → 설명]에 `{{차트}}` | 그림 교체 |
| 배경 그림이 있는 표 칸에 `{{사진1}}` | 칸 배경 사진 교체(없으면 행 삭제) |

[스크린샷 자리: 한글에서 {{필드}} 적는 모습]

등록 후 `library/templates/<양식ID>/schema.yaml`에서 필드별 `binding`(자료에서 자동으로 채울 경로), `guide`(분량·문체),
`max_chars`를 고칠 수 있습니다. 코드 수정 없이 양식만 다시 등록하면 됩니다.

기본 양식 `aiboot_result_v1`은 「네이버클라우드 사옥투어 현장견학 결과보고서」의 서식을 그대로 두고 내용만 필드로 바꿔 만든 것입니다.

## 4. 한컴오피스 자동화 (HWP 변환·PDF 저장)

한컴오피스 2022는 프로그램이 파일을 열 때마다 **"한글을 이용하여 위 파일에 접근하려는 시도가 있습니다"** 창을 띄웁니다.
- 창이 뜨면 **[접근 허용]** 또는 **[모두 허용]** 을 누르세요. (응답이 없으면 120초 뒤 그 한글 프로세스를 닫고 대체 경로로 진행)
- 매번 묻지 않게 하려면: 한컴 개발자센터에서 **보안모듈(FilePathCheckerModuleExample.dll)** 을 받아 원하는 폴더에 두고
  `config/settings.yaml`의 `hancom.security_module_dll`에 그 경로를 적습니다. (현재 사용자 레지스트리
  `HKCU\Software\HNC\HwpAutomation\Modules`에 등록됨)
- 한컴이 없거나 응답이 없으면: .hwp는 텍스트만 추출(pyhwp), PDF는 LibreOffice+H2Orestart로 시도, 둘 다 없으면 안내 메시지.

## 5. 폴더 구조

```
config/settings.yaml          모델명·토큰·마스킹·PDF 변환기 순서
config/template_hints/         양식별 필드 기본 속성(binding, guide)
prompts/                       AI 프롬프트(코드와 분리)
library/templates/<양식ID>/    template.hwpx, original.*, schema.yaml
library/examples/<연도_사업명>/ source.*, extracted.md, meta.yaml, (plan.md)
library/style_profile.md       문체 프로필
projects/<YYYYMMDD_사업명>/     input/, work/(추출물·json·로그), output/(hwpx, pdf, 근거보고서.md)
src/reportgen/                 ingest · library · analyze · generate · validate · render · ui
```

## 6. 문제 해결

| 증상 | 확인 |
|---|---|
| "AI 미연결" | `.env`에 `ANTHROPIC_API_KEY` 입력 후 run.bat 재실행 |
| 과거 PDF가 "텍스트 없음" | 한글에서 PDF로 인쇄한 파일은 글꼴 정보가 깨져 글자를 읽을 수 없습니다. 원본 .hwp/.hwpx를 등록하거나 API 키를 넣고 다시 등록(비전으로 읽음) |
| HWP 변환·PDF가 오래 걸리다 실패 | 4장의 한컴 보안 창 확인 |
| 생성 hwpx가 안 열림 | `work/logs/`와 함께 문의. 텍스트 칸만 채운 안전 모드는 `schema.yaml`에서 해당 표/블록 필드를 지우고 재생성 |
| 숫자 경고("근거 없는 숫자") | 초안 숫자가 올린 자료에서 확인되지 않음 → 자료 추가 또는 문장 수정 |
