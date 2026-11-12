@echo off
chcp 65001 > nul
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo [설치] 가상환경을 만드는 중입니다. 처음 한 번만 몇 분 걸립니다...
  py -3.12 -m venv .venv 2>nul || python -m venv .venv
  .venv\Scripts\python -m pip install -r requirements.txt
)
if not exist .env copy .env.example .env > nul
echo ReportGen 을 시작합니다. 잠시 후 크롬이 자동으로 열립니다. 종료하려면 이 창을 닫으세요.
rem 서버가 뜰 시간을 기다린 뒤 크롬으로 연다. 크롬이 없으면 기본 브라우저로 연다.
start "" /b cmd /c "timeout /t 4 /nobreak > nul & (start "" chrome http://localhost:8501 || start "" http://localhost:8501)"
.venv\Scripts\python -m streamlit run app.py --server.headless true --browser.gatherUsageStats false
pause
