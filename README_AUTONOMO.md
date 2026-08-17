# 🚀 Sistema Autônomo Prime Fazendas

Automação completa para publicação de conteúdo. **Zero comandos manuais. Zero travas.**

## ⚡ Como Usar (Rápido)

### 1️⃣ Iniciar (UMA VEZ)

**Windows (PowerShell):**
```powershell
# Abra a pasta do repositório
# Clique direito > Abrir PowerShell aqui
# Cole isto:
powershell -ExecutionPolicy Bypass -File ".\INICIAR_WATCH.ps1"
```

Ou **duplo clique** em: `INICIAR_WATCH.bat`

**Linux/Mac:**
```bash
bash INICIAR_WATCH.sh
```

Uma janelinha abre e fica monitorando 24/7. **Pode minimizar e esquecer.**

### 2️⃣ Usar

Simplesmente **diga para Claude**:

```
"cria um artigo sobre agricultura de precisão"
"publica uma notícia sobre a safra"
"atualiza a página de contato com novo endereço"
```

Claude vai:
1. ✅ Criar conteúdo em HTML/JSON
2. ✅ Validar SEO e integridade
3. ✅ Salvar em staging
4. ✅ Criar arquivo `_PUBLISH.flag`

O **watcher detecta em ~45s** e:
1. 📤 Faz commit + push
2. 🌐 Vercel publica (~1 min)
3. ✅ Verifica ao vivo
4. 📝 Registra tudo no changelog

### 3️⃣ Monitorar

Abra `VERSOES/AUTONOMO_WATCH_LOG.md`:

```markdown
- `2026-08-12 14:32:15` — **SUCCESS** — Publicação automática completada
- `2026-08-12 14:32:00` — **PUBLISH** — Flag detectada, iniciando publicação
- `2026-08-12 14:31:45` — **INFO** — Monitorando...
```

---

## 📁 Estrutura de Pastas

```
prime-fazendas-website/
│
├── INICIAR_WATCH.ps1              ← Clique aqui para iniciar (Windows)
├── INICIAR_WATCH.sh               ← Execute isto para iniciar (Linux/Mac)
├── INICIAR_WATCH.bat              ← Duplo clique (Windows)
│
├── _PUBLISH.flag                  ← Sistema detecta isto (~45s) e publica
│
├── infra/
│   ├── config.json                ← Configurações do sistema
│   └── .env                       ← Tokens (NUNCA versionado!)
│
├── AUTONOMO/
│   ├── watcher.js                 ← Núcleo: monitora arquivos
│   ├── publisher.js               ← Publica: commit + push
│   ├── validator.js               ← Valida conteúdo
│   └── generator.js               ← Integração com Claude
│
├── data/
│   ├── articles.json              ← Metadata de artigos
│   ├── noticias.json              ← Metadata de notícias
│   └── content-staging/           ← Conteúdo aguardando publicação
│
├── VERSOES/
│   ├── AUTONOMO_WATCH_LOG.md      ← Histórico de publicações
│   ├── changelog.md               ← Changelog automático
│   └── backup-YYYY-MM-DD-HHMMSS/  ← Backups automáticos
│
└── [arquivos do site...]
    ├── index.html
    ├── about.html
    ├── contact.html
    └── ...
```

---

## 🔄 Fluxo Automático

```
Você diz: "publica um artigo sobre solos de Goiás"
   ↓
Claude cria HTML + metadata
   ↓
Sistema salva em staging + cria _PUBLISH.flag
   ↓
Watcher detecta em ~45s
   ↓
✅ Commit automático
✅ Push para GitHub
✅ Vercel publica (~1 min)
✅ Verifica ao vivo (Chrome)
✅ Confirma no log

Resultado: "no ar" ✅
```

---

## 🛡️ Segurança

- ✅ Tokens em `infra/.env` (NUNCA versionado)
- ✅ Backup automático antes de cada publicação
- ✅ Changelog automático
- ✅ Log completo em `AUTONOMO_WATCH_LOG.md`
- ✅ Sistema pode ser pausado a qualquer hora
- ✅ Apenas o sistema publica (sem cliques manuais)

---

## 📋 Configuração

Arquivo: `infra/config.json`

```json
{
  "github": {
    "repo": "afiac1988/prime-fazendas-website",
    "branch": "main"
  },
  "vercel": {
    "auto_deploy": true,
    "site_url": "https://primefazendas.com/"
  },
  "watcher": {
    "check_interval_seconds": 45,
    "flag_file": "_PUBLISH.flag"
  },
  "backup": {
    "enabled": true,
    "before_publish": true
  }
}
```

---

## 🎯 Comandos Avançados

### Publicar Agora (sem esperar 45s)

**PowerShell:**
```powershell
cd C:\seu\caminho\prime-fazendas-website
New-Item -Name "_PUBLISH.flag" -ItemType File -Force
```

**Bash:**
```bash
cd /seu/caminho/prime-fazendas-website
touch _PUBLISH.flag
```

### Ver Histórico de Publicações

```bash
cat VERSOES/AUTONOMO_WATCH_LOG.md
```

### Pausar Sistema

Feche a janela do watcher. Ele vai parar de monitorar.

### Retomar Sistema

Execute `INICIAR_WATCH.ps1` ou `INICIAR_WATCH.sh` novamente.

---

## 🆘 Problemas Comuns

### ❌ "Arquivo não encontrado"
- Verifique se está na pasta correta: `C:\PA—AI CORE\ANDAR_07 — Prime Fazendas\prime-fazendas-website\`
- Verifique se tem `.git/` dentro (é um repositório)

### ❌ "PowerShell não executa scripts"
- Execute como administrador
- Execute: `Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process`

### ❌ "Git/GitHub CLI não encontrado"
- Instale Git: https://git-scm.com/download
- Instale GitHub CLI: https://cli.github.com/
- Autentique: `gh auth login`

### ❌ "Vercel não publica em 1 minuto"
- Espere mais 30-60 segundos
- Verifique em: https://app.vercel.com/
- Clear cache do navegador: Ctrl+Shift+Delete

### ❌ "Watcher não detecta mudanças"
- Verifique se `_PUBLISH.flag` existe
- Verifique se está na pasta correta
- Reinicie o watcher

---

## 📊 Exemplo de Log

```markdown
## 🚀 Publicações Automáticas

### 2026-08-12 14:45:32
- **Tipo**: Artigo
- **Título**: "Solos de Goiás - Análise Completa"
- **Status**: ✅ NO AR
- **URL**: https://primefazendas.com/artigo-solos-goias.html
- **Commit**: a1b2c3d...
- **Verificado ao vivo**: SIM
- **Tempo total**: 2m 15s (conteúdo + publicação)

### 2026-08-12 13:20:15
- **Tipo**: Notícia
- **Título**: "Safra 2026 - Perspectivas Positivas"
- **Status**: ✅ NO AR
- **URL**: https://primefazendas.com/noticias/safra-2026
- **Commit**: e4f5g6h...
- **Verificado ao vivo**: SIM
- **Tempo total**: 1m 45s
```

---

## 🎓 Fluxo Passo-a-Passo

### Criar um Novo Artigo

1. **Você**: Peça para Claude criar um artigo
   ```
   "cria um artigo sobre agricultura de precisão em Goiás,
    com título, imagem, 2000 palavras, SEO otimizado"
   ```

2. **Claude**: Cria e salva em `data/content-staging/`
   ```
   ✅ artigo-agricultura-precisao.html (criado)
   ✅ Validado: SEO, links, imagens
   ✅ Metadata adicionada em articles.json
   ```

3. **Você**: Confirma publicação
   ```
   "publica esse artigo"
   ```

4. **Sistema**: Cria flag e detecta em 45s
   ```
   ✅ _PUBLISH.flag criado
   ✅ Detectado (45s)
   ✅ Commit: "chore: atualização automática..."
   ✅ Push para GitHub
   ✅ Vercel compilando...
   ✅ No ar em 1m
   ✅ Verificado ao vivo
   ✅ Log atualizado
   ```

5. **Resultado**: Artigo está no ar
   ```
   https://primefazendas.com/artigo-agricultura-precisao.html
   ```

---

## 🔧 Integração com Claude

Quando você pedir para criar conteúdo:

```python
# Claude recebe: "publica um artigo"
# Claude faz:
1. Gera HTML limpo + SEO
2. Cria metadata em JSON
3. Salva em data/content-staging/
4. Atualiza articles.json
5. Cria _PUBLISH.flag
# Retorna: "Pronto! O watcher vai publicar em ~45s"
```

---

## 📈 Próximos Passos

- [ ] Iniciar watcher (execute `INICIAR_WATCH.ps1`)
- [ ] Pedir para Claude criar um artigo
- [ ] Confirmar publicação
- [ ] Aguardar ~2 minutos
- [ ] Verificar site ao vivo
- [ ] Pronto! Repetir para próximo conteúdo

---

## ✅ Benefícios

| Antes | Depois |
|-------|--------|
| ❌ Manual: comando no terminal | ✅ Automático: detecta em 45s |
| ❌ Vários passos | ✅ Um clique (ou só falar) |
| ❌ Sem backup | ✅ Backup automático |
| ❌ Sem log | ✅ Changelog automático |
| ❌ Sem verificação | ✅ Verifica ao vivo |
| ❌ Tempo perdido | ✅ 100% eficiente |

---

## 🎉 Status

```
✅ Sistema pronto
✅ Monitoramento ativo
✅ Pronto para primeira publicação
✅ Zero configuração necessária
```

**Deixe o watcher rodando e esqueça de scripts!**

---

**Sistema Autônomo Prime Fazendas v1.0**
*Eficiência total. Automatização completa.*
