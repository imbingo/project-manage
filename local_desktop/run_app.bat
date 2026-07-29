@echo off
cd /d "%~dp0"
echo Checking dependencies...
python -c "import PySide6, openpyxl, pptx" 2>nul
if errorlevel 1 (
    echo Installing dependencies, please wait...
    python -m pip install -r requirements.txt
)
echo Starting Project_Manage_LocalV3.6...
python main.py
if errorlevel 1 pause
