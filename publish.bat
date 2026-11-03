@echo off
rem TaxPulse - publish this folder to github.com/khalilhafsa/taxpulse (private files stay on this computer).
cd /d "%~dp0"
where git >nul 2>&1 || (echo Git is not installed. & pause & exit /b 1)
if not exist .git git init -b main
git config user.name "khalil hafsa"
git config user.email "khalilhafsa@users.noreply.github.com"
rem Remove leftovers from earlier versions (they break the public build).
for %%f in (frontend\src\components\MatchList.tsx frontend\src\pages\Evaluation.tsx frontend\src\pages\Placeholder.tsx backend\app\agents\prefilter.py backend\app\routes\matching.py doc\SPEC.md) do if exist %%f del /q %%f
if exist doc rmdir doc >nul 2>&1
git add -A
rem Safety check: never publish the API key, the database or uploaded files.
git ls-files | findstr /r /i "^\.env$ taxpulse\.db$ ^data/uploads/ \.venv/ node_modules/" >nul
if not errorlevel 1 (
  echo STOP: a private file was about to be published. Nothing was sent. Tell Claude.
  git ls-files | findstr /r /i "^\.env$ taxpulse\.db$ ^data/uploads/ \.venv/ node_modules/"
  pause & exit /b 1
)
git commit -q -m "Update TaxPulse" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -m "Claude-Session: https://claude.ai/code/session_01Xa8BQysy54hgwBPA8D3tZM" || echo Nothing new to commit.
git remote remove origin >nul 2>&1
git remote add origin https://github.com/khalilhafsa/taxpulse.git
echo Connecting to GitHub (a browser window may ask you to sign in)...
git pull -q origin main --allow-unrelated-histories --no-edit >nul 2>&1
git push -u origin main
if errorlevel 1 (
  echo The upload did not work. Take a screenshot of this window and send it to Claude.
) else (
  echo Done. Open https://github.com/khalilhafsa/taxpulse
)
pause
