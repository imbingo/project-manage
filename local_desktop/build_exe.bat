@echo off
setlocal
cd /d "%~dp0"
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --windowed --name Project_Manage_LocalV3.2 --add-data "src;src" main.py
echo Built dist\Project_Manage_LocalV3.2\Project_Manage_LocalV3.2.exe
pause
