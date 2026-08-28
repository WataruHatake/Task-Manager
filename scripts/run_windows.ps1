$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonw = Join-Path $projectRoot ".venv\Scripts\pythonw.exe"

if (-not (Test-Path $pythonw)) {
    throw "仮想環境がありません。先にscripts\setup_windows.cmdを実行してください。"
}

Start-Process -FilePath $pythonw -ArgumentList "-m", "dandori" -WorkingDirectory $projectRoot

