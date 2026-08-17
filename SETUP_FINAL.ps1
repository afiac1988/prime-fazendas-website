# ============================================================================
# SISTEMA AUTÔNOMO - WATCHER PRINCIPAL (PowerShell)
# ============================================================================
# Este script monitora a pasta e publica automaticamente quando detecta
# o arquivo _PUBLISH.flag. Executar UMA VEZ, depois deixa rodando.
# ============================================================================

$ErrorActionPreference = "Stop"

# ============================================================================
# SETUP INICIAL
# ============================================================================

$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$REPO_ROOT = $SCRIPT_DIR
$AUTONOMO_DIR = Join-Path $REPO_ROOT "AUTONOMO"
$INFRA_DIR = Join-Path $REPO_ROOT "infra"
$VERSOES_DIR = Join-Path $REPO_ROOT "VERSOES"
$LOG_FILE = Join-Path $VERSOES_DIR "AUTONOMO_WATCH_LOG.md"
$FLAG_FILE = Join-Path $REPO_ROOT "_PUBLISH.flag"
$CONFIG_FILE = Join-Path $INFRA_DIR "config.json"

# Criar diretórios se não existirem
@($AUTONOMO_DIR, $INFRA_DIR, $VERSOES_DIR) | ForEach-Object {
    if (-not (Test-Path $_)) {
        New-Item -ItemType Directory -Path $_ -Force | Out-Null
    }
}

# ============================================================================
# BANNER
# ============================================================================

Write-Host "╔═══════════════════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║                   🚀 SISTEMA AUTÔNOMO - PRIME FAZENDAS                       ║" -ForegroundColor Cyan
Write-Host "║                                                                               ║" -ForegroundColor Cyan
Write-Host "║  Status: ATIVO E MONITORANDO                                                 ║" -ForegroundColor Green
Write-Host "║  Monitora: $REPO_ROOT" -ForegroundColor Cyan
Write-Host "║  Log: $LOG_FILE" -ForegroundColor Cyan
Write-Host "║                                                                               ║" -ForegroundColor Cyan
Write-Host "║  ℹ️  Deixe esta janela aberta (pode minimizar)                              ║" -ForegroundColor Yellow
Write-Host "║  ℹ️  Qualquer mudança será detectada em ~45 segundos                        ║" -ForegroundColor Yellow
Write-Host "║                                                                               ║" -ForegroundColor Cyan
Write-Host "╚═══════════════════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ============================================================================
# FUNÇÃO: LOGAR
# ============================================================================

function Log-Event {
    param(
        [string]$Message,
        [string]$Status = "INFO",
        [string]$Color = "White"
    )

    $Timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    $Entry = "[$Timestamp] [$Status] $Message"

    Write-Host $Entry -ForegroundColor $Color

    # Adicionar ao arquivo de log markdown
    $MarkdownEntry = "- ``$($Timestamp)`` — **$Status** — $Message"
    Add-Content -Path $LOG_FILE -Value $MarkdownEntry -Encoding UTF8
}

# ============================================================================
# FUNÇÃO: PUBLICAR
# ============================================================================

function Publish-Changes {
    Write-Host ""
    Write-Host "📤 PUBLICANDO..." -ForegroundColor Yellow
    Write-Host ""

    Push-Location $REPO_ROOT

    try {
        # 1. Verificar status
        Write-Host "   ✓ Verificando status..." -ForegroundColor Cyan
        $status = git status --short

        if ([string]::IsNullOrWhiteSpace($status)) {
            Log-Event "Nenhuma mudança para publicar" "SKIP" "Yellow"
            Pop-Location
            return
        }

        Write-Host "   ✓ Mudanças detectadas:" -ForegroundColor Green
        $status | ForEach-Object { Write-Host "     $_" -ForegroundColor Green }

        # 2. Criar backup
        Write-Host "   ✓ Criando backup..." -ForegroundColor Cyan
        $BackupDir = Join-Path $VERSOES_DIR ("backup-" + (Get-Date).ToString("yyyy-MM-dd-HHmmss"))
        New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
        Copy-Item -Path (Join-Path $REPO_ROOT "*.html") -Destination $BackupDir -Force -ErrorAction SilentlyContinue
        Copy-Item -Path (Join-Path $REPO_ROOT "*.json") -Destination $BackupDir -Force -ErrorAction SilentlyContinue
        Copy-Item -Path (Join-Path $REPO_ROOT "*.md") -Destination $BackupDir -Force -ErrorAction SilentlyContinue
        Write-Host "   ✓ Backup criado em: $BackupDir" -ForegroundColor Green

        # 3. Git add + commit
        Write-Host "   ✓ Fazendo commit..." -ForegroundColor Cyan
        git add .

        $CommitMessage = "chore: atualização automática via Sistema Autônomo ($((Get-Date).ToString('yyyy-MM-dd HH:mm:ss')))"
        git commit -m $CommitMessage

        if ($LASTEXITCODE -eq 0) {
            Write-Host "   ✓ Commit criado" -ForegroundColor Green
        } else {
            Write-Host "   ⚠️  Nenhuma mudança nova para commitar" -ForegroundColor Yellow
            Log-Event "Commit falhou (nenhuma mudança)" "WARN" "Yellow"
            Pop-Location
            return
        }

        # 4. Git push
        Write-Host "   ✓ Enviando para GitHub..." -ForegroundColor Cyan
        git push origin main

        if ($LASTEXITCODE -eq 0) {
            Write-Host "   ✓ Push concluído" -ForegroundColor Green
            Log-Event "Publicação automática completada com sucesso" "SUCCESS" "Green"
        } else {
            Write-Host "   ❌ Erro ao fazer push" -ForegroundColor Red
            Log-Event "Erro no push para GitHub" "ERROR" "Red"
        }

        # 5. Aguardar Vercel
        Write-Host "   ✓ Aguardando Vercel (estimado: ~1 minuto)..." -ForegroundColor Cyan

        # 6. Verificar ao vivo (exemplo básico)
        Start-Sleep -Seconds 2
        Write-Host "   ✓ Tentando verificar site ao vivo..." -ForegroundColor Cyan

        try {
            $response = Invoke-WebRequest -Uri "https://primefazendas.com/" -TimeoutSec 10 -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                Write-Host "   ✅ SITE VERIFICADO AO VIVO!" -ForegroundColor Green
                Log-Event "Site verificado ao vivo - Status: 200 OK" "SUCCESS" "Green"
            }
        } catch {
            Write-Host "   ⚠️  Não conseguiu acessar site (pode ser normal)" -ForegroundColor Yellow
        }

    } catch {
        Write-Host "   ❌ Erro durante publicação: $_" -ForegroundColor Red
        Log-Event "Erro durante publicação: $_" "ERROR" "Red"
    } finally {
        Pop-Location
    }

    Write-Host ""
}

# ============================================================================
# LOOP PRINCIPAL: MONITORAR E PUBLICAR
# ============================================================================

$LastCheck = (Get-Date).AddSeconds(-10)
$CheckInterval = 45  # segundos

Log-Event "Sistema Autônomo iniciado e monitorando..." "START" "Green"

while ($true) {
    try {
        $Now = Get-Date

        # Verificar se é hora de checar
        if (($Now - $LastCheck).TotalSeconds -ge $CheckInterval) {
            $LastCheck = $Now

            # Verificar se arquivo de flag existe
            if (Test-Path $FLAG_FILE) {
                Write-Host ""
                Write-Host "🚨 ARQUIVO DE PUBLICAÇÃO DETECTADO!" -ForegroundColor Yellow
                Write-Host ""

                # Remover flag
                Remove-Item $FLAG_FILE -Force
                Log-Event "Flag de publicação detectada - iniciando publicação" "PUBLISH" "Yellow"

                # Executar publicação
                Publish-Changes

                Write-Host ""
                Write-Host "✅ Aguardando próxima ordem..." -ForegroundColor Green
                Write-Host ""
            }

            # Mostrar status a cada 5 verificações
            if (([int]((Get-Date)).Second) % 15 -eq 0) {
                $timestamp = (Get-Date).ToString("HH:mm:ss")
                Write-Host "⏰ $timestamp — Monitorando..." -ForegroundColor DarkGray -NoNewline
                Write-Host ""
            }
        }

        # Aguardar antes da próxima verificação
        Start-Sleep -Milliseconds 1000

    } catch {
        Write-Host "❌ Erro no loop: $_" -ForegroundColor Red
        Log-Event "Erro no loop principal: $_" "ERROR" "Red"
        Start-Sleep -Seconds 5
    }
}

# ============================================================================
# ENCERRAMENT
# ============================================================================
Write-Host ""
Write-Host "Encerrando Sistema Autônomo..." -ForegroundColor Yellow
Log-Event "Sistema Autônomo encerrado" "STOP" "Yellow"
