$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$dataRoot = "D:\TaskManager\Data"
$virtualEnv = Join-Path $projectRoot ".venv"

if (-not (Test-Path "D:\")) {
    throw "Dドライブを確認できません。Dドライブが利用可能か確認してください。"
}

$pythonCommand = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCommand = @("py", "-3.12")
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCommand = @("python")
} else {
    throw "Python 3.12.2を確認できません。"
}

$version = if ($pythonCommand.Count -eq 2) {
    & $pythonCommand[0] $pythonCommand[1] --version
} else {
    & $pythonCommand[0] --version
}
if ($LASTEXITCODE -ne 0) {
    throw "Python 3.12の起動に失敗しました。"
}
if ($version -notmatch "Python 3\.12\.") {
    throw "Python 3.12が必要です。検出結果: $version"
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
        throw "Python仮想環境の作成に失敗しました。"
    }
}

$venvPython = Join-Path $virtualEnv "Scripts\python.exe"
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "pipの更新に失敗しました。"
}
& $venvPython -m pip install -e $projectRoot
if ($LASTEXITCODE -ne 0) {
    throw "DANDORIの必要ライブラリ導入に失敗しました。"
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
        Write-Warning "Noto Sans JPを取得できませんでした。Windows標準フォントで起動します。"
    }
}

$bootstrapDir = Join-Path $env:LOCALAPPDATA "TaskManager"
$bootstrapFile = Join-Path $bootstrapDir "bootstrap.json"
New-Item -ItemType Directory -Force -Path $bootstrapDir | Out-Null
@{ data_dir = $dataRoot } |
    ConvertTo-Json |
    Set-Content -Encoding UTF8 $bootstrapFile

Write-Host ""
Write-Host "DANDORIのセットアップが完了しました。" -ForegroundColor Green
Write-Host "データ保存先: $dataRoot"
Write-Host "起動: scripts\run_windows.cmd"
