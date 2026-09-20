# Auditoria técnica completa — 2026-09-20

Espelho curto do registro completo, que vive no Obsidian (fonte de verdade):
`PROJETOS/SITE_DIGITAL/04_REGISTROS/2026-09-20-auditoria-tecnica-completa.md`, e no
doc do Projeto Claude `AG2_SITE_DIGITAL_PRIME_FAZENDAS`.

Commits: `5d08382` (correções) e `1b3579f` (limpeza de escopo — remove pasta
"Claude outputs/" adicionada por engano). Ambos locais, aguardando `git push` manual
do Andre (bloqueio de credenciais do sandbox, sem solução possível deste lado).

Resumo das correções aplicadas em `build.py`:
- `hreflang_para()`: reciprocidade de hreflang corrigida em 9 pontos de geração de página PT.
- `/blog/` registrada em `PAGINAS_TRADUZIDAS` (faltava).
- Link da marca no rodapé i18n corrigido para `/{lang}/`.
- Categoria "Bem-estar" adicionada a `CATEGORIA_I18N`.
- `IMOVEIS_I18N_MAP_ATUAL` (variável global) refatorada para parâmetro explícito.

0 links/imagens quebrados, 281 blocos JSON-LD válidos, 0 duplicidades de title/description,
em 213 páginas. Ver registro completo para o detalhamento e as melhorias sugeridas (fora
do escopo desta rodada).
