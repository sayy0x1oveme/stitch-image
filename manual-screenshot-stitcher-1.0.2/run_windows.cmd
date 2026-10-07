@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto use_python
set "STITCH_PY=py -3"
goto check_python
:use_python
where python >nul 2>nul
if errorlevel 1 goto no_python
set "STITCH_PY=python"
:check_python
%STITCH_PY% -c "import sys; print('Using Python', sys.version.split()[0]); sys.exit(0 if sys.version_info >= (3,10) else 1)"
if errorlevel 1 goto old_python
%STITCH_PY% -c "import tkinter; import PIL"
if errorlevel 1 goto missing_dependencies
%STITCH_PY% manual_stitch.py
if errorlevel 1 echo Application failed. Please copy the error above when reporting a bug.
pause
exit /b
:no_python
echo Python was not found. Install Python 3.10 or newer with Tkinter and the Python launcher.
pause
exit /b 1
:old_python
echo Python 3.10 or newer is required. Update Python and try again.
pause
exit /b 1
:missing_dependencies
echo Pillow or Tkinter is missing. Install dependencies using:
echo %STITCH_PY% -m pip install -r requirements.txt
echo Tkinter is included with the standard Windows Python installation.
pause
exit /b 1
