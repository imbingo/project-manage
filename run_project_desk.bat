@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"

if /I "%~1"=="web" goto web
if /I "%~1"=="desktop" goto desktop

echo Project Desk launcher
echo.
echo [1] Web app in browser
echo [2] Local desktop app
echo.
set /p MODE=Choose mode [1]:
if "%MODE%"=="2" goto desktop

:web
call :find_python
if errorlevel 1 goto no_python

set PORT=8080

:find_port
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, %PORT%); $listener.Start(); $listener.Stop(); exit 0 } catch { exit 1 }" >nul 2>nul
if errorlevel 1 (
    set /a PORT+=1
    if !PORT! LEQ 8090 goto find_port
    echo No free local port found from 8080 to 8090.
    pause
    exit /b 1
)

set URL=http://localhost:!PORT!/
echo Starting Project Desk web app at !URL!
start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 1; Start-Process '!URL!'"
%PYTHON_CMD% -m http.server !PORT!
if errorlevel 1 pause
exit /b %ERRORLEVEL%

:desktop
if not exist "%~dp0local_desktop\main.py" (
    echo Missing local_desktop\main.py.
    pause
    exit /b 1
)

call :find_desktop_python
if errorlevel 1 goto no_python

pushd "%~dp0local_desktop"
echo Checking desktop dependencies...
%PYTHON_CMD% -c "import PySide6, openpyxl" 2>nul
if errorlevel 1 (
    echo Installing PySide6 and openpyxl, please wait...
    %PYTHON_CMD% -m pip install PySide6 openpyxl
    if errorlevel 1 (
        set DESKTOP_EXIT=%ERRORLEVEL%
        popd
        pause
        exit /b %DESKTOP_EXIT%
    )
)

echo Starting Project_Manage_LocalV3.1...
%PYTHON_CMD% main.py
set DESKTOP_EXIT=%ERRORLEVEL%
popd
if not "%DESKTOP_EXIT%"=="0" pause
exit /b %DESKTOP_EXIT%

:find_python
where py >nul 2>nul
if not errorlevel 1 (
    set PYTHON_CMD=py -3
    exit /b 0
)

where python >nul 2>nul
if not errorlevel 1 (
    set PYTHON_CMD=python
    exit /b 0
)

exit /b 1

:find_desktop_python
py -3.13 --version >nul 2>nul
if not errorlevel 1 (
    set PYTHON_CMD=py -3.13
    exit /b 0
)

py -3 --version >nul 2>nul
if not errorlevel 1 (
    set PYTHON_CMD=py -3
    exit /b 0
)

where python >nul 2>nul
if not errorlevel 1 (
    set PYTHON_CMD=python
    exit /b 0
)

exit /b 1

:no_python
echo Python was not found. Install Python 3, or add it to PATH, then run this file again.
pause
exit /b 1
