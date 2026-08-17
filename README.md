# Prime Fazendas — site

Site institucional e portfólio de imóveis rurais da Prime Fazendas.
O fluxo canônico hoje é:

`conteudo/` ou `tema/assets/` → `ver.ps1` → commit em `main` → push → Vercel publica.

**No ar em:** https://primefazendas.com

> Mapa rápido e atualizado do fluxo: [MAPA_RAPIDO_VERCEL.md](MAPA_RAPIDO_VERCEL.md)

---

## O que editar

### Conteúdo

- `conteudo/config.json` — contatos, redes e configuração do site
- `conteudo/paginas.json` — textos institucionais
- `conteudo/dados-agro.json` — indicadores do setor
- `conteudo/depoimentos.json` — prova social
- `conteudo/imoveis/*.json` — propriedades
- `conteudo/noticias/*.md` — artigos do blog

### Aparência e comportamento

- `tema/assets/estilo.css` — estilo visual
- `tema/assets/site.js` — menu e interações
- `tema/assets/marca.svg` — marca vetorial gerada
- `tema/assets/og-prime-fazendas.png` — imagem de compartilhamento gerada

### Geração e publicação

- `build.py` — gera a pasta `site/`
- `ver.ps1` — preview local, sem publicar; no modo `-Demo` usa pasta temporária e não mexe no `site/` versionado
- `vercel.json` — configuração da publicação na Vercel

---

## O que não mexer manualmente

- `site/` — saída gerada pelo build
- arquivos legados de publicação antiga — foram removidos do fluxo canônico

---

## Como atualizar

1. Edite o arquivo certo em `conteudo/` ou `tema/assets/`.
2. Rode `ver.ps1` para conferir localmente.
3. Se estiver certo, faça commit na branch `main`.
4. Dê push.
5. A Vercel publica automaticamente.

## Antes de publicar

Confira os dois pontos que mais travam o fluxo:

- `conteudo/config.json` — troque os dados de contato de teste pelos reais
- `manutencao.local.json` — se estiver ativo, preencha a senha e o caminho absoluto do `.htpasswd`; para teste local, deixe desativado

---

## Estrutura curta

```text
prime-fazendas-website/
├── conteudo/
├── tema/assets/
├── build.py
├── ver.ps1
├── vercel.json
├── site/
└── MAPA_RAPIDO_VERCEL.md
```

---

## Requisitos

- Python 3.10+
- Git
- Navegador para validar o site local

---

## Regra principal

Se a mudança for de conteúdo, vá em `conteudo/`.
Se a mudança for visual, vá em `tema/assets/`.
Se a mudança for de publicação, o caminho é Vercel via `main`.
