param(
    [string]$Version = "Project_Manage_LocalV3.6"
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

$InstallBat = Join-Path $SetupSrc "install_project_manage_v3.6.bat"
@"
@echo off
setlocal
set "APP_DIR=%LOCALAPPDATA%\Programs\Project_Manage_LocalV3.6"
if not exist "%APP_DIR%" mkdir "%APP_DIR%"
copy /Y "%~dp0$ExeName" "%APP_DIR%\$ExeName" >nul
powershell -NoProfile -ExecutionPolicy Bypass -Command "`$desktop=[Environment]::GetFolderPath('Desktop');`$shortcut=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path `$desktop 'Project Manage Local V3.6.lnk'));`$shortcut.TargetPath=(Join-Path `$env:LOCALAPPDATA 'Programs\Project_Manage_LocalV3.6\$ExeName');`$shortcut.WorkingDirectory=(Join-Path `$env:LOCALAPPDATA 'Programs\Project_Manage_LocalV3.6');`$shortcut.IconLocation=`$shortcut.TargetPath;`$shortcut.Save()"
echo Project Manage Local V3.6 installed to "%APP_DIR%".
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
FinishMessage=Project Manage Local V3.6 installed.
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
FriendlyName="Project Manage Local V3.6 Setup"
AppLaunched="install_project_manage_v3.6.bat"
PostInstallCmd="<None>"
FILE0="$ExeName"
FILE1="install_project_manage_v3.6.bat"
"@

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $IExpressSed) | Out-Null
$Sed | Set-Content -Encoding ASCII $IExpressSed
iexpress.exe /N /Q $IExpressSed

if (!(Test-Path $SetupPath)) {
    Write-Warning "IExpress did not create setup package. Falling back to embedded C# installer."
    $InstallerSource = Join-Path $SetupSrc "ProjectManageInstaller.cs"
    $Cs = @'
using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Windows.Forms;

class ProjectManageInstaller
{
    [STAThread]
    static int Main()
    {
        try
        {
            string version = "__VERSION__";
            string exeName = version + ".exe";
            string appDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", version);
            Directory.CreateDirectory(appDir);
            string targetExe = Path.Combine(appDir, exeName);
            using (Stream source = Assembly.GetExecutingAssembly().GetManifestResourceStream("payload.exe"))
            {
                if (source == null) throw new InvalidOperationException("Installer payload is missing.");
                using (FileStream target = File.Create(targetExe))
                {
                    source.CopyTo(target);
                }
            }
            string command = "$desktop=[Environment]::GetFolderPath('Desktop');" +
                "$shortcut=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $desktop 'Project Manage Local V3.6.lnk'));" +
                "$shortcut.TargetPath='" + targetExe.Replace("'", "''") + "';" +
                "$shortcut.WorkingDirectory='" + appDir.Replace("'", "''") + "';" +
                "$shortcut.IconLocation=$shortcut.TargetPath;" +
                "$shortcut.Save()";
            ProcessStartInfo info = new ProcessStartInfo("powershell.exe", "-NoProfile -ExecutionPolicy Bypass -Command \"" + command.Replace("\"", "\\\"") + "\"");
            info.UseShellExecute = false;
            info.CreateNoWindow = true;
            Process process = Process.Start(info);
            process.WaitForExit();
            MessageBox.Show("Project Manage Local V3.6 installed to:\n\n" + appDir, "Project Manage Local V3.6 Setup", MessageBoxButtons.OK, MessageBoxIcon.Information);
            return 0;
        }
        catch (Exception ex)
        {
            MessageBox.Show(ex.Message, "Project Manage Local V3.6 Setup Failed", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
'@
    $Cs = $Cs.Replace("__VERSION__", $Version.Replace("\", "\\").Replace('"', '\"'))
    $Cs | Set-Content -Encoding UTF8 $InstallerSource
    $Csc = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"
    if (!(Test-Path $Csc)) {
        $Csc = Join-Path $env:WINDIR "Microsoft.NET\Framework\v4.0.30319\csc.exe"
    }
    if (!(Test-Path $Csc)) {
        throw "Setup package was not created and csc.exe was not found."
    }
    & $Csc /nologo /target:winexe /out:$SetupPath /win32icon:$IconPath /resource:"$(Join-Path $SetupSrc $ExeName),payload.exe" /reference:System.Windows.Forms.dll $InstallerSource
    if ($LASTEXITCODE -ne 0) {
        throw "Fallback setup compiler failed."
    }
}

if (!(Test-Path $SetupPath)) {
    throw "Setup package was not created: $SetupPath"
}

Write-Host "Built setup: $SetupPath"
