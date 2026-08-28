$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$dataRoot = "D:\TaskManager\Data"
$virtualEnv = Join-Path $projectRoot ".venv"

if (-not (Test-Path "D:\")) {
    throw "D drive was not found. Make sure the D drive is available."
}

$pythonCommand = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCommand = @("py", "-3.12")
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCommand = @("python")
} else {
    throw "Python 3.12 was not found."
}

$version = if ($pythonCommand.Count -eq 2) {
    & $pythonCommand[0] $pythonCommand[1] --version
} else {
    & $pythonCommand[0] --version
}
if ($LASTEXITCODE -ne 0) {
    throw "Failed to start Python 3.12."
}
if ($version -notmatch "Python 3\.12\.") {
    throw "Python 3.12 is required. Detected: $version"
}

New-Item -ItemType Directory -Force -Path $dataRoot | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $dataRoot "attachments") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $dataRoot "migration_backup") | Out-Null

if (-not (Test-Path $virtualEnv)) {
    if ($pythonCommand.Count -eq 2) {
        & $pythonCommand[0] $pythonCommand[1] -m venv $virtualEnv
    } else {
        & $pythonCommand[0] -m venv $virtualEnv
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create the Python virtual environment."
    }
}

$venvPython = Join-Path $virtualEnv "Scripts\python.exe"
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "Failed to upgrade pip."
}
& $venvPython -m pip install -e $projectRoot
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install DANDORI dependencies."
}

$fontDir = Join-Path $projectRoot "src\dandori\assets\fonts"
$fontFile = Join-Path $fontDir "NotoSansJP-Variable.ttf"
if (-not (Test-Path $fontFile)) {
    New-Item -ItemType Directory -Force -Path $fontDir | Out-Null
    try {
        Invoke-WebRequest `
            -UseBasicParsing `
            -Uri "https://raw.githubusercontent.com/google/fonts/main/ofl/notosansjp/NotoSansJP%5Bwght%5D.ttf" `
            -OutFile $fontFile
    } catch {
        Write-Warning "Noto Sans JP could not be downloaded. DANDORI will use a Windows system font."
    }
}

$bootstrapDir = Join-Path $env:LOCALAPPDATA "TaskManager"
$bootstrapFile = Join-Path $bootstrapDir "bootstrap.json"
New-Item -ItemType Directory -Force -Path $bootstrapDir | Out-Null
@{ data_dir = $dataRoot } |
    ConvertTo-Json |
    Set-Content -Encoding UTF8 $bootstrapFile

$venvPythonw = Join-Path $virtualEnv "Scripts\pythonw.exe"
$shortcutShell = New-Object -ComObject WScript.Shell
function New-DandoriShortcut {
    param(
        [string]$ShortcutPath,
        [string]$Mode
    )
    $shortcut = $shortcutShell.CreateShortcut($ShortcutPath)
    $shortcut.TargetPath = $venvPythonw
    $shortcut.Arguments = "-m dandori --mode $Mode"
    $shortcut.WorkingDirectory = $projectRoot
    $shortcut.IconLocation = "$venvPythonw,0"
    $shortcut.Save()
}

$desktopDir = [Environment]::GetFolderPath("Desktop")
New-DandoriShortcut (Join-Path $desktopDir "DANDORI.lnk") "full"
New-DandoriShortcut (Join-Path $desktopDir "DANDORI Add.lnk") "add"
New-DandoriShortcut (Join-Path $desktopDir "DANDORI Tasks.lnk") "tasks"

$startupDir = [Environment]::GetFolderPath("Startup")
New-DandoriShortcut (Join-Path $startupDir "DANDORI.lnk") "tray"

Start-Process `
    -FilePath $venvPythonw `
    -ArgumentList "-m", "dandori", "--mode", "tray" `
    -WorkingDirectory $projectRoot

Write-Host ""
Write-Host "DANDORI setup completed." -ForegroundColor Green
Write-Host "Data directory: $dataRoot"
Write-Host "Start command: scripts\run_windows.cmd"
Write-Host "Desktop shortcuts and Windows startup registration were created."
Write-Host "DANDORI is now running in the notification area."
