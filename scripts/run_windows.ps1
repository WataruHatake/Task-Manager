$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonw = Join-Path $projectRoot ".venv\Scripts\pythonw.exe"

if (-not (Test-Path $pythonw)) {
    throw "Virtual environment was not found. Run scripts\setup_windows.cmd first."
}

Start-Process -FilePath $pythonw -ArgumentList "-m", "dandori" -WorkingDirectory $projectRoot
