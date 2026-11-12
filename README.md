# ReportGen — 결과보고 자동생성 프로그램

결과보고 양식(.hwpx)과 과거 결과보고서를 라이브러리로 등록해 두고, 새 행사의 **계획안 + 결과 자료**를 넣으면
양식에 맞는 **결과보고서(.hwpx + PDF)** 와 **근거보고서(.md)** 를 만듭니다.

- 숫자(인원·합계·달성률·만족도 비율)는 **프로그램이 계산**하고, AI는 문장만 씁니다.
- 자료에 없는 내용은 지어내지 않고 `[확인 필요: 사유]`로 남깁니다.
- 모든 파일은 이 PC에만 저장되며, AI로 보내기 전 이름·전화·이메일·학번을 가립니다(기본 켜짐).

## 1. 설치·실행

> 이 프로그램은 **내 PC에서만 실행하는 로컬 앱**입니다. 인터넷 서버(Vercel 등)에 올려서 쓰는 구조가 아닙니다.
> (한컴오피스를 직접 조종하고, 개인정보가 담긴 자료를 PC 밖으로 내보내지 않기 위해서입니다.)

### 1-1. 준비물 (새 PC에서 처음 한 번)

| 프로그램 | 필수 여부 | 비고 |
|---|---|---|
| Windows 10/11 | 필수 | 한컴 자동화(`pywin32`) 때문에 Windows 전용 |
| [Python 3.12](https://www.python.org/downloads/) | 필수 | 설치할 때 **"Add python.exe to PATH" 체크** |
| [Git](https://git-scm.com/download/win) | 필수 | 프로젝트 내려받기·올리기용 |
| Google Chrome | 권장 | `run.bat`이 크롬으로 화면을 엶 (없으면 기본 브라우저) |
| 한컴오피스 2022 | 권장 | .hwp 읽기, PDF 저장에 사용. 없으면 4장의 대체 경로로 동작 |

### 1-2. 프로젝트 내려받기

PowerShell(또는 명령 프롬프트)에서:
```
cd D:\
git clone https://github.com/LimJongTak/report.git
cd report
```
> 폴더 위치는 어디든 됩니다. 아래 설명은 `D:\report` 기준입니다.

### 1-3. 실행

1. **`run.bat` 더블클릭**
   - 처음 실행하면 가상환경(`.venv`)을 만들고 필요한 패키지를 설치합니다(몇 분 걸림, 처음 한 번만).
   - `.env` 파일이 없으면 `.env.example`을 복사해 자동으로 만듭니다.
   - 몇 초 뒤 **크롬**에 `http://localhost:8501` 화면이 열립니다.
     "사이트에 연결할 수 없음"이 먼저 보이면 잠시 후 **F5(새로고침)** 하세요.
2. 종료: 검은 명령 창을 닫거나 그 창에서 `Ctrl + C`.

명령어로 직접 실행하려면:
```
cd D:\report
.venv\Scripts\activate
streamlit run app.py
```
(이 경우 크롬 주소창에 `localhost:8501`을 직접 입력)

### 1-4. AI 기능 켜기 (API 키)

1. https://console.anthropic.com 로그인 → **API Keys → Create Key** → `sk-ant-...` 키 복사
   (창을 닫으면 다시 볼 수 없으니 바로 복사)
2. **Billing**에서 결제 수단 등록 후 크레딧 충전 (선불 $5~10 정도면 충분, 다 쓰면 자동으로 멈춤)
3. `D:\report\.env`를 메모장으로 열어 아래처럼 저장 (띄어쓰기·따옴표 없이)
   ```
   ANTHROPIC_API_KEY=sk-ant-여기에키
   ```
4. `run.bat` 다시 실행

- 키가 없어도 실행됩니다. 이때는 자료·숫자 항목(일정표, 예산표, 인원, 만족도 집계·그래프, 사진)만 자동으로 채워지고
  문장 항목은 `[확인 필요: AI 미연결]`로 표시됩니다.
- **비용**: 사용한 만큼 과금. 기본 모델(`claude-sonnet-5-5`, 입력 100만 토큰당 $2 / 출력 $10) 기준
  보고서 1건에 대략 $0.2~0.5(300~700원) 정도입니다(자료 양에 따라 다름). 실제 사용액은 콘솔 **Usage**에서 확인.
  모델은 `config/settings.yaml`의 `model`에서 바꿉니다.
- `.env`는 Git에 올라가지 않습니다. **PC마다 따로 넣어야 합니다.** 키를 채팅·메일·코드에 붙여 넣지 마세요.

### 1-5. Git에 올라가지 않는 것 (다른 PC로 옮길 때 주의)

개인정보 보호를 위해 아래 파일은 `.gitignore`로 제외되어 있어 `git clone`으로 받아지지 않습니다.

| 경로 | 내용 | 새 PC에서 하는 법 |
|---|---|---|
| `.env` | API 키 | 1-4대로 새로 입력 |
| `projects/` | 진행한 결과보고 작업 전체(입력 자료·초안·결과물) | 필요하면 USB·클라우드로 **폴더째 복사** |
| `library/examples/*/source.*`, `extracted.md`, `plan.md`, `plan_source.*` | 과거 결과보고 원본과 추출 본문 | 폴더째 복사하거나, 원본 파일로 다시 등록(아래) |
| `library/templates/*/original.*` | 양식의 원본 파일 | 필요하면 복사 (`template.hwpx`·`schema.yaml`은 Git에 있음) |
| `.venv/` | 파이썬 가상환경 | `run.bat`이 자동으로 새로 만듦 |

과거 사례를 원본 파일로 다시 등록하는 방법:
```
.venv\Scripts\activate
python scripts/import_library.py --examples <과거보고서 폴더> [--plans <계획안 폴더>]
```
> 기존 PC의 `D:\report\projects`와 `D:\report\library` 폴더를 그대로 새 PC의 같은 위치에 덮어쓰면 가장 간단합니다.

### 1-6. 여러 PC에서 번갈아 작업할 때

작업 시작 전 (최신 코드 받기):
```
cd D:\report
git pull
```
`requirements.txt`가 바뀌었으면 패키지도 갱신:
```
.venv\Scripts\python -m pip install -r requirements.txt
```
작업 끝난 후 (변경 올리기):
```
git add -A
git commit -m "변경 내용 요약"
git push
```
> `git add -A`를 해도 `.env`·`projects/`·원본 파일은 `.gitignore` 덕분에 올라가지 않습니다.
> 처음 push할 때 GitHub 로그인 창이 뜨면 본인 계정으로 로그인하세요.

### 1-7. 개발자용 명령
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
| run.bat이 "python을 찾을 수 없음"으로 끝남 | Python 3.12 설치 시 "Add python.exe to PATH" 체크했는지 확인 후 재설치. 설치가 중간에 실패했다면 `.venv` 폴더를 지우고 run.bat 재실행 |
| 크롬이 안 열림 / "연결할 수 없음" | 검은 창에 오류가 없는지 확인 → 크롬에서 `localhost:8501` 직접 입력 후 F5 |
| "Port 8501 is already in use" | 이미 켜진 ReportGen 창이 있음. 그 창을 닫고 다시 실행 |
| `git pull` 후 오류 | `.venv\Scripts\python -m pip install -r requirements.txt`로 패키지 갱신 |
| "AI 미연결" | `.env`에 `ANTHROPIC_API_KEY` 입력 후 run.bat 재실행 |
| AI 오류 "credit balance is too low" | 콘솔 Billing에서 크레딧 충전 |
| 과거 PDF가 "텍스트 없음" | 한글에서 PDF로 인쇄한 파일은 글꼴 정보가 깨져 글자를 읽을 수 없습니다. 원본 .hwp/.hwpx를 등록하거나 API 키를 넣고 다시 등록(비전으로 읽음) |
| HWP 변환·PDF가 오래 걸리다 실패 | 4장의 한컴 보안 창 확인 |
| 생성 hwpx가 안 열림 | `work/logs/`와 함께 문의. 텍스트 칸만 채운 안전 모드는 `schema.yaml`에서 해당 표/블록 필드를 지우고 재생성 |
| 숫자 경고("근거 없는 숫자") | 초안 숫자가 올린 자료에서 확인되지 않음 → 자료 추가 또는 문장 수정 |
