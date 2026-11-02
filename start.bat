@echo off
rem TaxPulse - start the backend and the frontend, then open the browser once the backend answers.
cd /d "%~dp0"
if not exist backend\.venv (
  echo Run setup.bat first.
  pause & exit /b 1
)
start "TaxPulse API" cmd /k "cd /d "%~dp0backend" && .venv\Scripts\python -m uvicorn app.main:app --reload --port 8000"
start "TaxPulse UI" cmd /k "cd /d "%~dp0frontend" && npm run dev"
echo Starting TaxPulse... waiting for the backend (up to 90 seconds).
powershell -NoProfile -Command "for($i=0;$i -lt 90;$i++){try{Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/health -TimeoutSec 2 | Out-Null; exit 0}catch{Start-Sleep 1}}; exit 1"
if errorlevel 1 (
  echo The backend did not start. Look at the "TaxPulse API" window for the error, or run diagnose.bat.
  pause & exit /b 1
)
echo Backend ready. Opening TaxPulse.
start "" http://localhost:5173
