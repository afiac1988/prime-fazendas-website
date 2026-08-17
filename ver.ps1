# =============================================================================
#  Prime Fazendas — VER O SITE NO COMPUTADOR (sem publicar nada)
#
#  Uso:  .\ver.ps1
#
#  Gera o site a partir de conteudo/ e abre no navegador em http://127.0.0.1:8099
#  No modo -Demo, a prévia é gerada numa pasta temporária separada do site/
#  versionado, para não correr o risco de misturar rascunho com publicação.
# =============================================================================

param([switch]$Demo)

$ErrorActionPreference = 'Stop'
$raiz = $PSScriptRoot
Set-Location $raiz

$porta = 8099

function Achar-Python {
    foreach ($c in @('python', 'py', 'C:\Python314\python.exe')) {
        $cmd = Get-Command $c -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source }
    }
    return $null
}

$python = Achar-Python
if (-not $python) {
    Write-Host ""
    Write-Host "  Python nao encontrado." -ForegroundColor Red
    Write-Host "  Instale em https://www.python.org/downloads/ marcando 'Add to PATH'."
    Write-Host ""
    exit 1
}

$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

$saidaPreview = Join-Path ([System.IO.Path]::GetTempPath()) ("prime-fazendas-preview-" + ([guid]::NewGuid().ToString("N")))
if (-not (Test-Path $saidaPreview)) {
    New-Item -ItemType Directory -Path $saidaPreview -Force | Out-Null
}

Write-Host ""
Write-Host "  Gerando o site..." -ForegroundColor Cyan
if ($Demo) {
    Write-Host "  (modo rascunho: mostrando tambem o que esta com publicado=false)" -ForegroundColor Yellow
    & $python "$raiz\build.py" --demo --saida $saidaPreview
} else {
    & $python "$raiz\build.py"
}
$codigo = $LASTEXITCODE

if ($codigo -ne 0) {
    Write-Host "  (ha bloqueios acima — para ver localmente tudo bem, mas o fluxo de publicacao vai recusar)" -ForegroundColor Yellow
}

# Derruba um servidor antigo na mesma porta, se houver
$emUso = Get-NetTCPConnection -LocalPort $porta -State Listen -ErrorAction SilentlyContinue
if ($emUso) {
    foreach ($c in $emUso) {
        try { Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue } catch {}
    }
    Start-Sleep -Milliseconds 400
}

Write-Host "  Servindo em http://127.0.0.1:$porta" -ForegroundColor Green
Write-Host "  Feche esta janela (ou Ctrl+C) para parar." -ForegroundColor DarkGray
Write-Host ""

Start-Process "http://127.0.0.1:$porta"

if ($Demo) {
    Set-Location $saidaPreview
} else {
    Set-Location "$raiz\site"
}
& $python -m http.server $porta --bind 127.0.0.1
