@echo off
setlocal
cd /d "%~dp0"
py -3 -m pip install -r requirements.txt -r requirements-build.txt
if errorlevel 1 goto done
py -3 -m PyInstaller --noconfirm --clean --onefile --windowed --name ManualScreenshotStitcher exe_entry.py
:done
pause
