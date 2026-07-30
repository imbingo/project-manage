param(
    [string]$Version = "Project_Manage_LocalV3.6.1"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Dist = Join-Path $Root "dist"
$SetupSrc = Join-Path $Root "build\setup_src"
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
    static int Main(string[] args)
    {
        bool quiet = false;
        foreach (string arg in args)
        {
            string normalized = (arg ?? "").Trim().ToLowerInvariant();
            if (normalized == "/q" || normalized == "/quiet" || normalized == "/silent")
            {
                quiet = true;
            }
        }

        try
        {
            string version = "__VERSION__";
            string exeName = version + ".exe";
            string appDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", version);
            Directory.CreateDirectory(appDir);

            string targetExe = Path.Combine(appDir, exeName);
            using (Stream source = Assembly.GetExecutingAssembly().GetManifestResourceStream("payload.exe"))
            {
                if (source == null)
                {
                    throw new InvalidOperationException("Installer payload is missing.");
                }
                using (FileStream target = File.Create(targetExe))
                {
                    source.CopyTo(target);
                }
            }

            string shortcutName = "Project Manage Local V3.6.1.lnk";
            string command =
                "$desktop=[Environment]::GetFolderPath('Desktop');" +
                "$shortcut=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $desktop '" + shortcutName.Replace("'", "''") + "'));" +
                "$shortcut.TargetPath='" + targetExe.Replace("'", "''") + "';" +
                "$shortcut.WorkingDirectory='" + appDir.Replace("'", "''") + "';" +
                "$shortcut.IconLocation=$shortcut.TargetPath;" +
                "$shortcut.Save()";
            ProcessStartInfo info = new ProcessStartInfo("powershell.exe", "-NoProfile -ExecutionPolicy Bypass -Command \"" + command.Replace("\"", "\\\"") + "\"");
            info.UseShellExecute = false;
            info.CreateNoWindow = true;
            Process process = Process.Start(info);
            process.WaitForExit();
            if (process.ExitCode != 0)
            {
                throw new InvalidOperationException("Shortcut creation failed.");
            }

            if (!quiet)
            {
                MessageBox.Show("Project Manage Local V3.6.1 installed to:\n\n" + appDir, "Project Manage Local V3.6.1 Setup", MessageBoxButtons.OK, MessageBoxIcon.Information);
            }
            return 0;
        }
        catch (Exception ex)
        {
            if (!quiet)
            {
                MessageBox.Show(ex.Message, "Project Manage Local V3.6.1 Setup Failed", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
            Console.Error.WriteLine(ex.ToString());
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
    throw "csc.exe was not found; cannot build setup package."
}

& $Csc /nologo /target:winexe /out:$SetupPath /win32icon:$IconPath /resource:"$(Join-Path $SetupSrc $ExeName),payload.exe" /reference:System.Windows.Forms.dll $InstallerSource
if ($LASTEXITCODE -ne 0) {
    throw "Setup compiler failed."
}
if (!(Test-Path $SetupPath)) {
    throw "Setup package was not created: $SetupPath"
}

Write-Host "Built setup: $SetupPath"
