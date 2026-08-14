# Gera tudo o que vai para o usuario final: icone, executavel e instalador.
#
#   .\tools\build.ps1
#
# Requisitos: o ambiente virtual em .venv (com as dependencias de dev) e o
# Inno Setup 6 instalado.

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$python = Join-Path $root '.venv\Scripts\python.exe'
$pyinstaller = Join-Path $root '.venv\Scripts\pyinstaller.exe'
$icon = Join-Path $root 'src\slidecut\assets\icon.ico'

$iscc = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not (Test-Path $python)) { throw "ambiente virtual nao encontrado em $python" }

Write-Host '==> Gerando o icone' -ForegroundColor Cyan
& $python tools\make_icon.py

Write-Host '==> Rodando os testes' -ForegroundColor Cyan
& $python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'os testes falharam; build interrompido' }

Write-Host '==> Empacotando o executavel' -ForegroundColor Cyan
& $pyinstaller --noconfirm --onefile --windowed `
    --name slidecut `
    --icon $icon `
    --paths src `
    --add-data "src\slidecut\assets\icon.ico;slidecut\assets" `
    entry_gui.py
if ($LASTEXITCODE -ne 0) { throw 'o PyInstaller falhou' }

if (-not $iscc) {
    Write-Warning 'Inno Setup 6 nao encontrado; instalador nao foi gerado.'
    Write-Host "Pronto: $root\dist\slidecut.exe" -ForegroundColor Green
    exit 0
}

Write-Host '==> Compilando o instalador' -ForegroundColor Cyan
& $iscc installer\slidecut.iss
if ($LASTEXITCODE -ne 0) { throw 'o Inno Setup falhou' }

Write-Host ''
Write-Host 'Pronto:' -ForegroundColor Green
Get-ChildItem dist\*.exe | ForEach-Object {
    '  {0}  ({1:N1} MB)' -f $_.Name, ($_.Length / 1MB)
}
