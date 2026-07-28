param(
    [string]$Version = "Project_Manage_LocalV3.4"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Dist = Join-Path $Root "dist"
$SetupSrc = Join-Path $Root "build\setup_src"
$IExpressSed = Join-Path $Root "build\setup.iexpress.sed"
$ExeName = "$Version.exe"
$SetupName = "${Version}_Setup.exe"
$SetupPath = Join-Path $Dist $SetupName
$IconPath = Join-Path $Root "assets\project_manage.ico"

Set-Location $Root
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --clean --windowed --onefile --name $Version --icon $IconPath --add-data "assets;assets" main.py

if (Test-Path $SetupSrc) {
    Remove-Item -Recurse -Force $SetupSrc
}
New-Item -ItemType Directory -Force -Path $SetupSrc | Out-Null
Copy-Item -Force (Join-Path $Dist $ExeName) (Join-Path $SetupSrc $ExeName)

$InstallBat = Join-Path $SetupSrc "install_project_manage_v3.4.bat"
@"
@echo off
setlocal
set "APP_DIR=%LOCALAPPDATA%\Programs\Project_Manage_LocalV3.4"
if not exist "%APP_DIR%" mkdir "%APP_DIR%"
copy /Y "%~dp0$ExeName" "%APP_DIR%\$ExeName" >nul
powershell -NoProfile -ExecutionPolicy Bypass -Command "`$desktop=[Environment]::GetFolderPath('Desktop');`$shortcut=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path `$desktop 'Project Manage Local V3.4.lnk'));`$shortcut.TargetPath=(Join-Path `$env:LOCALAPPDATA 'Programs\Project_Manage_LocalV3.4\$ExeName');`$shortcut.WorkingDirectory=(Join-Path `$env:LOCALAPPDATA 'Programs\Project_Manage_LocalV3.4');`$shortcut.IconLocation=`$shortcut.TargetPath;`$shortcut.Save()"
echo Project Manage Local V3.4 installed to "%APP_DIR%".
exit /b 0
"@ | Set-Content -Encoding ASCII $InstallBat

$Sed = @"
[Version]
Class=IEXPRESS
SEDVersion=3
[Options]
PackagePurpose=InstallApp
ShowInstallProgramWindow=1
HideExtractAnimation=1
UseLongFileName=1
InsideCompressed=0
CAB_FixedSize=0
CAB_ResvCodeSigning=0
RebootMode=N
InstallPrompt=
DisplayLicense=
FinishMessage=Project Manage Local V3.4 installed.
TargetName=%TargetName%
FriendlyName=%FriendlyName%
AppLaunched=%AppLaunched%
PostInstallCmd=%PostInstallCmd%
AdminQuietInstCmd=
UserQuietInstCmd=
SourceFiles=SourceFiles
[SourceFiles]
SourceFiles0=$SetupSrc\
[SourceFiles0]
%FILE0%=
%FILE1%=
[Strings]
TargetName="$SetupPath"
FriendlyName="Project Manage Local V3.4 Setup"
AppLaunched="install_project_manage_v3.4.bat"
PostInstallCmd="<None>"
FILE0="$ExeName"
FILE1="install_project_manage_v3.4.bat"
"@

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $IExpressSed) | Out-Null
$Sed | Set-Content -Encoding ASCII $IExpressSed
iexpress.exe /N /Q $IExpressSed

if (!(Test-Path $SetupPath)) {
    throw "Setup package was not created: $SetupPath"
}

Write-Host "Built setup: $SetupPath"
