@echo off
setlocal
cd /d "%~dp0"
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --windowed --name Project_Manage_LocalV3.4 --icon "assets\project_manage.ico" --add-data "src;src" --add-data "assets;assets" main.py
echo Built dist\Project_Manage_LocalV3.4\Project_Manage_LocalV3.4.exe
pause
