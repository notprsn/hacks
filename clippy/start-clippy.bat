@echo off
setlocal
cd /d "%~dp0"

echo.
echo Clippy setup
echo.

where py >nul 2>nul
if not errorlevel 1 goto :use_py

where python >nul 2>nul
if errorlevel 1 goto :no_python
set "PYTHON=python"
goto :check_python

:use_py
set "PYTHON=py -3"

:check_python
%PYTHON% -c "import sys; raise SystemExit(sys.version_info < (3, 10))"
if %errorlevel% neq 0 goto :old_python

if not exist ".venv\Scripts\python.exe" (
  echo 1/2 - Creating Clippy's private setup...
  %PYTHON% -m venv .venv
  if %errorlevel% neq 0 goto :failed
)

echo 2/2 - Installing or updating Clippy...
".venv\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check --upgrade -r requirements.txt
if %errorlevel% neq 0 goto :failed

echo.
echo Setup complete. Opening Clippy...
echo Keep this window open while you use it. Press Ctrl+C here to stop.
echo.
".venv\Scripts\python.exe" clippy.py
goto :end

:no_python
echo Python 3 is not installed.
echo Install it from https://www.python.org/downloads/ and run this file again.
start "" "https://www.python.org/downloads/"
goto :pause

:old_python
echo Clippy needs Python 3.10 or newer.
echo Update Python at https://www.python.org/downloads/ and run this file again.
start "" "https://www.python.org/downloads/"
goto :pause

:failed
echo.
echo Setup stopped. Check the error above, then run this file again.

:pause
echo.
pause

:end
endlocal
