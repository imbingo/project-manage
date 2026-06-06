@echo off
setlocal
cd /d "%~dp0"
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --windowed --name ProjectDeskLocal --add-data "src;src" main.py
echo Built dist\ProjectDeskLocal\ProjectDeskLocal.exe
pause
