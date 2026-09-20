# Atualização — Tradução completa das 35 propriedades (EN/ZH) + wiring i18n de imóveis

**Data:** 2026-09-20

## O que foi feito nesta atualização

1. Traduzidas para inglês e chinês simplificado as **35 fazendas publicadas** no
   portfólio (título, subtítulo, descrição completa, características,
   infraestrutura e documentação), preservando nomenclatura de pedras
   preciosas de forma consistente (ex.: Ágata → Agate / 玛瑙, Diamante →
   Diamond / 钻石, Turquesa → Turquoise / 绿松石). Traduções salvas em
   `conteudo/imoveis_i18n.json`, sem alterar os 35 arquivos-fonte em
   `conteudo/imoveis/*.json` (para não arriscar corromper anúncios comerciais
   ativos).
2. Construídos no `build.py` os templates i18n de imóveis:
   `card_imovel_i18n`, `gerar_lista_imoveis_i18n`, `gerar_ficha_imovel_i18n`,
   além dos dicionários `TIPOS_I18N`, `STATUS_I18N` e `TEXTOS_IMOVEL_I18N`
   (EN/ZH) que traduzem toda a UI ao redor dos dados (rótulos, filtros,
   ordenação, ficha técnica, breadcrumbs, JSON-LD).
3. Fotos, preços, áreas, coordenadas de mapa e vídeos são **exatamente os
   mesmos** da versão em português — só o texto muda.
4. Wiring completo no pipeline principal:
   - `/en/imoveis/` e `/zh/imoveis/` (listagens traduzidas, com os mesmos
     filtros e ordenação da versão PT).
   - `/en/imoveis/<slug>/` e `/zh/imoveis/<slug>/` para cada uma das 35
     fazendas.
   - `PAGINAS_TRADUZIDAS` agora inclui `/imoveis/` e a URL de cada ficha
     individual, então o seletor de idioma (bandeiras) funciona corretamente
     tanto na listagem quanto dentro de cada ficha de fazenda.
   - Menu (`NAV_I18N`) atualizado: "Properties"/"房产项目" agora apontam
     para as listagens traduzidas em vez de cair de volta para a versão PT.
   - Sitemap atualizado com as 72 novas URLs (35 fichas × 2 idiomas + 2
     listagens).
5. Validação: todos os 72 blocos de JSON-LD gerados (RealEstateListing +
   CollectionPage/ItemList) passaram em `json.loads()`; hreflang recíproco
   (pt-BR/en/zh-Hans/x-default) conferido em amostras; links do seletor de
   idioma conferidos nos dois sentidos (PT→EN/ZH e EN/ZH→PT).

## Build

`python3 build.py` → 157 páginas geradas, 35 imóveis, 27 artigos, sem
bloqueios. 3 avisos não-bloqueantes (mídia da fazenda-pirita, indicadores
pendentes de verificação em dados-agro.json, sem depoimentos publicados —
nenhum desses é novo nesta atualização).

## Ainda pendente (próxima frente)

- Tradução do Blog (27 posts em `conteudo/noticias/*.md`) para EN/ZH.
- Tradução da página "Investir no Agro" (`conteudo/dados-agro.json`).
- Push para o GitHub: **este ambiente não tem credenciais do GitHub
  configuradas** (sem `gh` CLI, sem credential helper). O commit foi feito
  localmente; o push para `origin main` precisa ser feito manualmente pelo
  usuário a partir do terminal, GitHub Desktop ou VS Code — para então
  disparar o deploy automático no Vercel.

## Sobre Obsidian / memória local

Nesta sessão não foi encontrado nenhum vault do Obsidian (nenhuma pasta
`.obsidian` nem pasta chamada "memória"/"memory") em nenhuma das duas pastas
conectadas (`prime-fazendas-website` e `PUBLICAR SITE`). Os locais que
realmente guardam o histórico desta atualização hoje são:

1. Este arquivo, dentro do próprio repositório (`docs/`) — viaja junto com
   o código, em todo `git pull`/`git clone`.
2. O documento no Claude Project "AG2_SITE_DIGITAL_PRIME_FAZENDAS"
   (`notas/2026-09-19-lancamento-pagina-data-center.md`), atualizado com o
   changelog completo.

Se o usuário tiver um vault do Obsidian em outra pasta do computador, essa
pasta precisa ser conectada a uma sessão futura para que os registros sejam
espelhados lá também.
