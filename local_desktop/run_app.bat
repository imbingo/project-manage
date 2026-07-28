@echo off
cd /d "%~dp0"
echo Checking dependencies...
python -c "import PySide6" 2>nul
if errorlevel 1 (
    echo Installing PySide6 and openpyxl, please wait...
    python -m pip install PySide6 openpyxl
)
echo Starting Project_Manage_LocalV3.3...
python main.py
if errorlevel 1 pause
