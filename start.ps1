$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Не удалось создать Python venv.' }
}
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
& $python -c 'import fastapi, uvicorn, demoparser2, importlib, sys; importlib.import_module("compression.zstd" if sys.version_info >= (3, 14) else "zstandard")'
if ($LASTEXITCODE -ne 0) {
    python -m pip --python $python install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Не удалось установить зависимости.' }
}
if (-not (Test-Path 'bin\weapon-scan.exe')) {
    if (Get-Command go -ErrorAction SilentlyContinue) {
        Push-Location 'tools\weapon-scan'
        try {
            go build -o '..\..\bin\weapon-scan.exe' .
            if ($LASTEXITCODE -ne 0) { Write-Warning 'Сканер оружия не собран; ножевые раунды останутся видимыми.' }
        } finally { Pop-Location }
    } else { Write-Warning 'Для сборки сканера ножевого раунда установите Go 1.26 или новее.' }
}
Write-Host 'CS2 Demo Lab: http://127.0.0.1:8000' -ForegroundColor Cyan
& $python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
