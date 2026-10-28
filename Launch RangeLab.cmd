@echo off
cd /d "%~dp0"
if exist "release\RangeLab\RangeLab.exe" (
  start "" "release\RangeLab\RangeLab.exe"
  exit /b
)
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" "rangelab.py"
  exit /b
)
echo Install Python requirements or build RangeLab first. See README.md.
pause
