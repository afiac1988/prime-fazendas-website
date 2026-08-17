# 🚀 SISTEMA AUTÔNOMO - Prime Fazendas Site

## Conceito

Assim como o projeto TORRE, o Prime Fazendas site terá um sistema **100% autônomo** que elimina etapas manuais repetitivas.

```
Você diz: "publica um artigo sobre agricultura de precisão"
   ↓
SISTEMA cria HTML, valida, otimiza SEO, insere em articles.json
   ↓
SISTEMA grava ordem de publicação (_PUBLISH.flag)
   ↓
SISTEMA WATCH percebe em ~45s e publica (commit + push)
   ↓
SISTEMA verifica ao vivo no Chrome e confirma: "no ar" ✅
```

## Estrutura de Pastas

```
prime-fazendas-website/
├── INICIAR_WATCH.bat              (DUPLO CLIQUE = tudo começa)
├── INICIAR_WATCH.sh               (versão Linux/Mac)
├── infra/
│   ├── .env                       (tokens, credenciais - NUNCA versionado)
│   ├── config.json                (configurações do sistema)
│   └── protections.json           (regras de segurança)
├── AUTONOMO/
│   ├── watcher.js                 (núcleo: monitora flags)
│   ├── publisher.js               (publica: commit + push + verifica)
│   ├── generator.js               (cria conteúdo com Claude)
│   ├── validator.js               (valida HTML, SEO, integridade)
│   └── log.md                     (histórico de todas publicações)
├── _PUBLISH.flag                  (bandeira: sistema detecta mudanças)
├── data/
│   ├── articles.json              (metadata de artigos)
│   └── content-staging/           (conteúdo aguardando publicação)
└── VERSOES/
    ├── changelog.md               (histórico de alterações)
    └── AUTONOMO_WATCH_LOG.md      (log do watcher automático)
```

## Fluxo de Funcionamento

### Passo 1: Iniciar (UMA VEZ)
```bash
# Windows
duplo clique em INICIAR_WATCH.bat

# Linux/Mac
bash INICIAR_WATCH.sh
```

Isto abre uma janelinha que fica monitorando 24/7. Pode minimizar e esquecer.

### Passo 2: Usar
Você simplesmente **diz para Claude**:

```
"publica um artigo sobre solos de Goiás"
"adiciona notícia sobre safra 2026"
"atualiza página de contato com novo telefone"
"cria landing page para evento de abril"
```

### Passo 3: Sistema Trabalha Automaticamente
1. **Generator** (Claude): cria conteúdo com IA
2. **Validator**: confere HTML, SEO, links
3. **Staging**: salva em `content-staging/`
4. **Flag**: cria `_PUBLISH.flag` quando pronto
5. **Watcher**: detecta flag em ~45s
6. **Publisher**: commit + push para GitHub
7. **Vercel**: publica automaticamente em ~1 min
8. **Verifier**: abre Chrome e confirma "no ar" ✅
9. **Log**: registra tudo em `AUTONOMO_WATCH_LOG.md`

## Segurança

```json
{
  "protections": {
    "token_location": "infra/.env",
    "token_never_exposed": true,
    "only_torre_can_publish": true,
    "backup_before_commit": true,
    "changelog_automatic": true,
    "logging_complete": true,
    "public_gate": "gate + noindex",
    "gate_review_at_launch": "reavaliamos juntos"
  }
}
```

## Configuração Inicial

Arquivo: `infra/config.json`

```json
{
  "github": {
    "repo": "afiac1988/prime-fazendas-website",
    "branch": "main",
    "auth_method": "cli"
  },
  "vercel": {
    "auto_deploy": true,
    "build_time_estimate": "~1 min"
  },
  "content": {
    "auto_seo": true,
    "auto_validate": true,
    "staging_folder": "data/content-staging"
  },
  "verification": {
    "check_live": true,
    "browser": "Chrome",
    "test_clickable": true,
    "test_images": true
  },
  "logging": {
    "watcher_log": "VERSOES/AUTONOMO_WATCH_LOG.md",
    "backup_before_publish": true,
    "changelog": "VERSOES/changelog.md"
  }
}
```

## Comandos Principais

### PowerShell (Windows)
```powershell
# Iniciar watcher (UMA VEZ)
.\INICIAR_WATCH.bat

# Comandos manuais (se necessário)
& "AUTONOMO\publisher.ps1"                  # publica agora
& "AUTONOMO\validator.ps1" -file "artigo.html"  # valida arquivo
Get-Content "VERSOES\AUTONOMO_WATCH_LOG.md" # vê histórico
```

### Bash (Linux/Mac)
```bash
# Iniciar watcher (UMA VEZ)
bash INICIAR_WATCH.sh

# Comandos manuais
node AUTONOMO/publisher.js
node AUTONOMO/validator.js
cat VERSOES/AUTONOMO_WATCH_LOG.md
```

## Integração com Claude

Quando você pedir para criar/atualizar conteúdo:

1. **Claude** recebe ordem → Gera HTML + metadata
2. **Sistema** salva em staging → Aguarda confirmação
3. **Você** diz "publica isso" → Sistema cria `_PUBLISH.flag`
4. **Watcher** detecta flag → Publica automaticamente

## Monitoramento

Abra `VERSOES/AUTONOMO_WATCH_LOG.md` a qualquer hora:

```markdown
## Publicações Automáticas

### 2026-08-12 14:32 ✅ PUBLICADO
- Artigo: "Solos de Goiás"
- Status: No ar em https://primefazendas.com/
- Commit: a1b2c3d
- Verificado ao vivo: SIM

### 2026-08-12 10:15 ✅ PUBLICADO
- Notícia: "Safra 2026"
- Status: No ar em https://primefazendas.com/noticias/
- Commit: e4f5g6h
- Verificado ao vivo: SIM
```

## Status Atual

- [ ] Criar estrutura de pastas
- [ ] Criar watcher.js/ps1
- [ ] Criar publisher.js/ps1
- [ ] Integrar com Claude
- [ ] Testar ciclo completo
- [ ] Documentar em README.md
- [ ] Deploy em produção

## Próximos Passos

1. **Setup Inicial**: Execute `INICIAR_WATCH.bat` UMA VEZ
2. **Usar**: Simplesmente peça para Claude criar conteúdo
3. **Monitorar**: Veja `AUTONOMO_WATCH_LOG.md` quando quiser
4. **Escalabilidade**: À medida que cresce, adicione mais tipos de conteúdo

---

**Objetivo**: Zero comandos manuais. Zero travas. 100% automático e seguro.
