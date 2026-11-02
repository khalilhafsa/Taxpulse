@echo off
rem TaxPulse - run the automated backend tests.
cd /d "%~dp0backend"
.venv\Scripts\python -m pytest -q
pause
