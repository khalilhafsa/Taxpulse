@echo off
rem TaxPulse - writes a diagnosis of the backend to data\diagnose.log (changes nothing)
cd /d "%~dp0backend"
set LOG="%~dp0data\diagnose.log"
echo ==== port 8000 (LISTENING means something already uses it) ==== > %LOG%
netstat -ano | findstr ":8000" | findstr "LISTENING" >> %LOG% 2>&1
echo ==== start-up test ==== >> %LOG%
.venv\Scripts\python diagnose_start.py >> %LOG% 2>&1
echo.
echo Done. Close this window and tell Claude: diagnose ok
pause
