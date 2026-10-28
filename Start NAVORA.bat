@echo off
setlocal
cd /d "%~dp0"
title NAVORA
echo.
echo  NAVORA - starting...
echo.

where python >nul 2>nul
if errorlevel 1 goto :nopython

if exist ".venv\Scripts\python.exe" goto :haveenv
echo  First run: setting up. This takes about a minute...
python -m venv .venv
if errorlevel 1 goto :fail
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
if errorlevel 1 goto :fail
:haveenv

if exist "instance\navora.db" goto :havedb
echo  Creating the database with demo data...
".venv\Scripts\python.exe" -m seed.seed
if errorlevel 1 goto :fail
echo.
echo  If an admin password was printed above, copy it now. It is shown only once.
echo.
:havedb

set PORT=5057
echo  Opening http://127.0.0.1:5057 in your browser.
echo  Keep this window open while using NAVORA. Close it to stop the app.
echo  Tip: click "Try the demo student" on the home page.
echo.
start "" /min cmd /c "timeout /t 3 /nobreak >nul & start http://127.0.0.1:5057"
".venv\Scripts\python.exe" run.py
goto :eof

:nopython
echo  Python was not found. Install Python 3.10 or newer from https://www.python.org/downloads/
echo  and tick "Add python.exe to PATH" during setup. Then double-click this file again.
pause
exit /b 1

:fail
echo.
echo  Setup failed. Please read the messages above.
pause
exit /b 1
