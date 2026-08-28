$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "仮想環境がありません。先にscripts\setup_windows.cmdを実行してください。"
}

Set-Location $projectRoot
& $python -m dandori

