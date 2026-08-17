# 📦 Guia de Deployment - Sistema Autônomo

## Arquivos Fornecidos

Você recebeu **6 arquivos** que implementam o sistema autônomo completo:

### 1️⃣ Documentação
- **AUTONOMO_SISTEMA.md** → Visão geral conceitual
- **README_AUTONOMO.md** → Guia completo de uso
- **DEPLOY_GUIA.md** → Este arquivo (instruções)

### 2️⃣ Watchers (Inicializadores)
- **INICIAR_WATCH.ps1** → PowerShell (Windows)
- **INICIAR_WATCH.sh** → Bash (Linux/Mac)
- **INICIAR_WATCH.bat** → Batch (Windows, duplo clique)

### 3️⃣ Configuração
- **infra-config.json** → Arquivo de configuração do sistema

---

## 🚀 Como Instalar (3 Passos)

### Passo 1: Copiar Arquivos

Copie **TODOS OS 6 ARQUIVOS** para a raiz do seu repositório:

```
C:\PA—AI CORE\ANDAR_07 — Prime Fazendas\prime-fazendas-website\
├── AUTONOMO_SISTEMA.md          ← Copiar aqui
├── README_AUTONOMO.md           ← Copiar aqui
├── INICIAR_WATCH.ps1            ← Copiar aqui
├── INICIAR_WATCH.sh             ← Copiar aqui
├── INICIAR_WATCH.bat            ← Copiar aqui
├── infra-config.json            ← Copiar aqui (renomear para infra/)
└── [arquivos existentes...]
```

**Importante**: O arquivo `infra-config.json` deve ser movido para a pasta `infra/`:

```bash
# Windows (PowerShell)
mkdir -p infra
move infra-config.json infra/config.json

# Linux/Mac
mkdir -p infra
mv infra-config.json infra/config.json
```

### Passo 2: Criar Estrutura de Diretórios

Abra PowerShell na pasta do repositório e execute:

```powershell
mkdir -p AUTONOMO
mkdir -p infra
mkdir -p VERSOES
mkdir -p data\content-staging
```

### Passo 3: Iniciar Watcher

**Opção A: Duplo Clique (Windows - Mais Fácil)**
1. Localize o arquivo `INICIAR_WATCH.bat`
2. Duplo clique nele
3. Uma janelinha abre e começa a monitorar

**Opção B: PowerShell (Windows)**
```powershell
# Na pasta do repositório
powershell -ExecutionPolicy Bypass -File ".\INICIAR_WATCH.ps1"
```

**Opção C: Bash (Linux/Mac)**
```bash
bash INICIAR_WATCH.sh
```

---

## ✅ Checklist de Validação

Após instalar, verifique se tudo está funcionando:

- [ ] Pasta `infra/` criada com `config.json`
- [ ] Pasta `AUTONOMO/` criada
- [ ] Pasta `VERSOES/` criada
- [ ] Pasta `data/content-staging/` criada
- [ ] Arquivo `INICIAR_WATCH.bat` (Windows) ou `.sh` (Linux/Mac)
- [ ] Watcher iniciado (janelinha aberta e monitorando)

---

## 🧪 Primeiro Teste

### 1. Deixe o Watcher Rodando

Execute `INICIAR_WATCH.ps1` (PowerShell) ou `INICIAR_WATCH.sh` (Bash).

Você deve ver:
```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                   🚀 SISTEMA AUTÔNOMO - PRIME FAZENDAS                       ║
║                                                                               ║
║  Status: ATIVO E MONITORANDO ✅                                              ║
```

### 2. Criar Flag de Publicação

Em **outro terminal** (deixe o watcher rodando), execute:

**Windows (PowerShell):**
```powershell
cd C:\PA—AI CORE\ANDAR_07 — Prime Fazendas\prime-fazendas-website
New-Item -Name "_PUBLISH.flag" -ItemType File -Force
```

**Linux/Mac:**
```bash
cd /seu/caminho/prime-fazendas-website
touch _PUBLISH.flag
```

### 3. Observar Publicação Automática

Volte para a janelinha do watcher e observe:

```
🚨 ARQUIVO DE PUBLICAÇÃO DETECTADO!

📤 PUBLICANDO...

   ✓ Verificando status...
   ✓ Mudanças detectadas:
   ✓ Criando backup...
   ✓ Fazendo commit...
   ✓ Enviando para GitHub...
   ✓ Aguardando Vercel...
   ✅ SITE VERIFICADO AO VIVO!

✅ Aguardando próxima ordem...
```

### 4. Verificar Log

Abra `VERSOES/AUTONOMO_WATCH_LOG.md`:

```markdown
- `2026-08-12 14:32:15` — **SUCCESS** — Publicação automática completada
- `2026-08-12 14:32:00` — **PUBLISH** — Flag detectada
```

✅ **Funcionando!**

---

## 🎯 Próximo Passo: Usar com Claude

Agora que o watcher está rodando, você pode simplesmente **pedir para Claude criar conteúdo**:

```
Cria um artigo de 2000 palavras sobre agricultura de precisão em Goiás,
com título atraente, SEO otimizado, uma imagem e dois CTAs.
Publica assim que terminar.
```

Claude vai:
1. ✅ Gerar HTML + metadata
2. ✅ Validar tudo
3. ✅ Salvar em `data/content-staging/`
4. ✅ Criar `_PUBLISH.flag`

O watcher detecta em ~45s e publica automaticamente!

---

## 🔧 Configurações Avançadas

### Mudar Intervalo de Detecção

Arquivo: `infra/config.json`

```json
{
  "watcher": {
    "check_interval_seconds": 45  ← Mudar aqui (padrão: 45)
  }
}
```

Valores possíveis:
- `15` = Verificação a cada 15s (mais rápido)
- `30` = Verificação a cada 30s (recomendado)
- `60` = Verificação a cada 1 minuto (mais lento)

### Mudar Repositório

```json
{
  "github": {
    "repo": "seu-usuario/seu-repo",  ← Mudar aqui
    "owner": "seu-usuario"            ← Mudar aqui
  }
}
```

---

## 🛟 Troubleshooting

### ❌ "PowerShell não executa scripts"

Execute como **administrador** e rode:

```powershell
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope CurrentUser
```

### ❌ "Arquivo não encontrado"

Verifique:
- Está na pasta correta? `C:\PA—AI CORE\ANDAR_07 — Prime Fazendas\prime-fazendas-website\`
- Tem `.git/` dentro? (É um repositório Git)

### ❌ "Git/GitHub CLI não encontrado"

Instale:
1. **Git**: https://git-scm.com/download
2. **GitHub CLI**: https://cli.github.com/

Depois autentique:
```bash
gh auth login
```

### ❌ "Watcher não detecta mudanças"

1. Verifique se `_PUBLISH.flag` foi criado
2. Verifique se está na pasta correta
3. Reinicie o watcher

---

## 📋 Estrutura Final Esperada

```
prime-fazendas-website/
│
├── 📄 AUTONOMO_SISTEMA.md        ✅ Copiado
├── 📄 README_AUTONOMO.md         ✅ Copiado
├── 🔧 INICIAR_WATCH.ps1          ✅ Copiado
├── 🔧 INICIAR_WATCH.sh           ✅ Copiado
├── 🔧 INICIAR_WATCH.bat          ✅ Copiado
│
├── 📁 infra/
│   └── 📄 config.json            ✅ Movido de infra-config.json
│
├── 📁 AUTONOMO/                  ✅ Criado
│   ├── watcher.js                (futuro: gerado por Claude se necessário)
│   └── ...
│
├── 📁 VERSOES/
│   ├── AUTONOMO_WATCH_LOG.md     ✅ Auto-criado pelo watcher
│   ├── changelog.md              ✅ Auto-criado
│   └── backup-*/                 ✅ Auto-criado
│
├── 📁 data/
│   └── 📁 content-staging/       ✅ Criado
│
└── [arquivos existentes...]
```

---

## 🎉 Pronto!

Seu sistema autônomo está **100% instalado e funcionando**.

### Resumo
- ✅ Watcher monitorando 24/7
- ✅ Publica automaticamente em ~45s
- ✅ Backup automático
- ✅ Changelog automático
- ✅ Log completo
- ✅ Zero configuração necessária

### Próximo Passo
Deixe o watcher rodando e comece a pedir conteúdo para Claude!

```
"cria um artigo sobre café especial"
```

Pronto! Em ~2 minutos, está no ar. ✅

---

**Sistema Autônomo Prime Fazendas — Pronto para Produção** 🚀
