# Mapa rápido — atualizar a Prime Fazendas na Vercel

Este é o caminho canônico para qualquer atualização do site hoje.

## Regra de ouro

- editar conteúdo em `conteudo/` ou aparência em `tema/assets/`
- gerar/validar localmente com `ver.ps1`
- commitar na branch `main`
- fazer push
- a Vercel publica automaticamente

## Onde mexer

### Conteúdo do site

- `conteudo/paginas.json` — textos institucionais
- `conteudo/config.json` — contatos, redes, domínio, analytics
- `conteudo/dados-agro.json` — indicadores e números do setor
- `conteudo/depoimentos.json` — prova social
- `conteudo/imoveis/*.json` — propriedades
- `conteudo/noticias/*.md` — blog

### Visual e interação

- `tema/assets/estilo.css` — aparência
- `tema/assets/site.js` — menus, filtros, comportamento
- `tema/assets/marca.svg` e `tema/assets/og-prime-fazendas.png` — identidade gerada

### Geração e publicação

- `build.py` — gera o site final
- `ver.ps1` — preview local, sem publicar
- `site/` — saída gerada; não editar manualmente
- `vercel.json` — diz para a Vercel publicar a pasta `site/`

## Caminho curto para uma alteração comum

1. abrir o arquivo certo em `conteudo/` ou `tema/assets/`
2. salvar a mudança
3. rodar `ver.ps1` para conferir
4. commitar no `main`
5. dar push
6. conferir o deploy na Vercel

## Antes de publicar

- confira `conteudo/config.json` e troque os contatos de teste pelos reais
- confira `manutencao.local.json`: se estiver ativo, preencha senha e caminho absoluto do `.htpasswd`; para teste local, deixe desativado

## O que não é mais o caminho principal

- o fluxo antigo de hospedagem fica como legado
- `site/` não é fonte de verdade; é resultado gerado
- qualquer instrução antiga de hospedagem fora da Vercel não deve ser usada no fluxo diário

## Se precisar localizar rapidamente

- texto institucional: `conteudo/paginas.json`
- imóveis: `conteudo/imoveis/`
- blog: `conteudo/noticias/`
- layout: `tema/assets/`
- publicação: Vercel via `main`

## Quando houver dúvida

Se a mudança for de conteúdo, vá em `conteudo/`.
Se a mudança for visual, vá em `tema/assets/`.
Se a mudança for de publicação, confira `vercel.json` e o deploy da Vercel.
