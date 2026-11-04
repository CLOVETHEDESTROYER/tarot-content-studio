@echo off
cd /d "%~dp0"
if exist "desktop-dist\StarPower Content Studio\StarPower Content Studio.exe" (
  start "" "desktop-dist\StarPower Content Studio\StarPower Content Studio.exe" --workspace "%~dp0."
) else (
  start "" ".venv\Scripts\pythonw.exe" "desktop.py" --workspace "%~dp0."
)
