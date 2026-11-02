@echo off
rem TaxPulse - one-time setup for Windows. Double-click this file.
cd /d "%~dp0"
echo.
echo === TaxPulse setup ===
echo.

set "PY=python3.13"
where python3.13 >nul 2>nul || set "PY=py -V:3.13"
%PY% --version >nul 2>nul || (
  echo [ERROR] Python 3.13 not found. Open PowerShell and run:  pymanager install 3.13
  pause & exit /b 1
)
where npm >nul 2>nul || (
  echo [ERROR] Node.js not found. Install the LTS version from https://nodejs.org then run this file again.
  pause & exit /b 1
)

echo [1/4] Creating Python environment...
if not exist backend\.venv %PY% -m venv backend\.venv || (echo [ERROR] Could not create the environment & pause & exit /b 1)

echo [2/4] Installing backend packages (a few minutes the first time)...
backend\.venv\Scripts\python -m pip install --upgrade pip >nul
backend\.venv\Scripts\python -m pip install -r backend\requirements.txt || (echo [ERROR] Backend install failed & pause & exit /b 1)

echo [3/4] Installing frontend packages...
pushd frontend
call npm install || (popd & echo [ERROR] Frontend install failed & pause & exit /b 1)
popd

echo [4/4] Creating settings file...
if not exist .env copy .env.example .env >nul

echo.
echo Setup complete. Double-click start.bat to launch TaxPulse.
pause
