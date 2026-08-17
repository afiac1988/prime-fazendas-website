#!/bin/bash
# ============================================================================
# SISTEMA AUTÔNOMO - WATCHER PRINCIPAL (Bash)
# ============================================================================
# Este script monitora a pasta e publica automaticamente quando detecta
# o arquivo _PUBLISH.flag. Executar UMA VEZ, depois deixa rodando.
# ============================================================================

set -e

# ============================================================================
# SETUP INICIAL
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$SCRIPT_DIR"
AUTONOMO_DIR="$REPO_ROOT/AUTONOMO"
INFRA_DIR="$REPO_ROOT/infra"
VERSOES_DIR="$REPO_ROOT/VERSOES"
LOG_FILE="$VERSOES_DIR/AUTONOMO_WATCH_LOG.md"
FLAG_FILE="$REPO_ROOT/_PUBLISH.flag"
CONFIG_FILE="$INFRA_DIR/config.json"

# Criar diretórios se não existirem
mkdir -p "$AUTONOMO_DIR" "$INFRA_DIR" "$VERSOES_DIR"

# ============================================================================
# BANNER
# ============================================================================

echo ""
echo "╔═══════════════════════════════════════════════════════════════════════════════╗"
echo "║                   🚀 SISTEMA AUTÔNOMO - PRIME FAZENDAS                       ║"
echo "║                                                                               ║"
echo "║  Status: ATIVO E MONITORANDO ✅                                              ║"
echo "║  Monitora: $REPO_ROOT"
echo "║  Log: $LOG_FILE"
echo "║                                                                               ║"
echo "║  ℹ️  Deixe este terminal aberto (pode minimizar)                            ║"
echo "║  ℹ️  Qualquer mudança será detectada em ~45 segundos                        ║"
echo "║                                                                               ║"
echo "╚═══════════════════════════════════════════════════════════════════════════════╝"
echo ""

# ============================================================================
# FUNÇÃO: LOGAR
# ============================================================================

log_event() {
    local message="$1"
    local status="${2:-INFO}"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local entry="- \`$timestamp\` — **$status** — $message"

    # Escrever no console
    case $status in
        "SUCCESS") echo "✅ [$timestamp] $message" ;;
        "ERROR")   echo "❌ [$timestamp] $message" ;;
        "WARN")    echo "⚠️  [$timestamp] $message" ;;
        "INFO")    echo "ℹ️  [$timestamp] $message" ;;
        *)         echo "   [$timestamp] $message" ;;
    esac

    # Adicionar ao arquivo de log markdown
    echo "$entry" >> "$LOG_FILE"
}

# ============================================================================
# FUNÇÃO: PUBLICAR
# ============================================================================

publish_changes() {
    echo ""
    echo "📤 PUBLICANDO..."
    echo ""

    cd "$REPO_ROOT"

    # 1. Verificar status
    echo "   ✓ Verificando status..."
    local status=$(git status --short)

    if [ -z "$status" ]; then
        log_event "Nenhuma mudança para publicar" "SKIP"
        return
    fi

    echo "   ✓ Mudanças detectadas:"
    echo "$status" | sed 's/^/     /'

    # 2. Criar backup
    echo "   ✓ Criando backup..."
    local backup_dir="$VERSOES_DIR/backup-$(date '+%Y-%m-%d-%H%M%S')"
    mkdir -p "$backup_dir"
    cp -r *.html "$backup_dir/" 2>/dev/null || true
    cp -r *.json "$backup_dir/" 2>/dev/null || true
    cp -r *.md "$backup_dir/" 2>/dev/null || true
    echo "   ✓ Backup criado em: $backup_dir"

    # 3. Git add + commit
    echo "   ✓ Fazendo commit..."
    git add .

    local commit_message="chore: atualização automática via Sistema Autônomo ($(date '+%Y-%m-%d %H:%M:%S'))"
    if git commit -m "$commit_message"; then
        echo "   ✓ Commit criado"
    else
        echo "   ⚠️  Nenhuma mudança nova para commitar"
        log_event "Commit falhou (nenhuma mudança)" "WARN"
        return
    fi

    # 4. Git push
    echo "   ✓ Enviando para GitHub..."
    if git push origin main; then
        echo "   ✓ Push concluído"
        log_event "Publicação automática completada com sucesso" "SUCCESS"
    else
        echo "   ❌ Erro ao fazer push"
        log_event "Erro no push para GitHub" "ERROR"
        return
    fi

    # 5. Aguardar Vercel
    echo "   ✓ Aguardando Vercel (estimado: ~1 minuto)..."
    sleep 2

    # 6. Verificar ao vivo (exemplo básico)
    echo "   ✓ Tentando verificar site ao vivo..."
    if curl -s -o /dev/null -w "%{http_code}" https://primefazendas.com/ | grep -q "200"; then
        echo "   ✅ SITE VERIFICADO AO VIVO!"
        log_event "Site verificado ao vivo - Status: 200 OK" "SUCCESS"
    else
        echo "   ⚠️  Não conseguiu acessar site (pode ser normal)"
    fi

    echo ""
}

# ============================================================================
# LOOP PRINCIPAL: MONITORAR E PUBLICAR
# ============================================================================

log_event "Sistema Autônomo iniciado e monitorando..." "START"

last_check=$(date +%s)
check_interval=45  # segundos

while true; do
    now=$(date +%s)
    elapsed=$((now - last_check))

    # Verificar se é hora de checar
    if [ $elapsed -ge $check_interval ]; then
        last_check=$now

        # Verificar se arquivo de flag existe
        if [ -f "$FLAG_FILE" ]; then
            echo ""
            echo "🚨 ARQUIVO DE PUBLICAÇÃO DETECTADO!"
            echo ""

            # Remover flag
            rm -f "$FLAG_FILE"
            log_event "Flag de publicação detectada - iniciando publicação" "PUBLISH"

            # Executar publicação
            publish_changes

            echo ""
            echo "✅ Aguardando próxima ordem..."
            echo ""
        fi
    fi

    # Mostrar heartbeat
    current_time=$(date '+%H:%M:%S')
    if [ $(($(date +%s) % 15)) -eq 0 ]; then
        echo -ne "⏰ $current_time — Monitorando...\r"
    fi

    # Aguardar antes da próxima verificação
    sleep 1
done
