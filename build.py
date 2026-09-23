#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prime Fazendas — gerador do site.

Lê conteudo/ e escreve site/. Zero dependências: só a biblioteca padrão do Python.

    python build.py                     gera o site
    python build.py --auditar            só valida o conteúdo e sai (não escreve nada)
    python build.py --demo --saida TMP   gera uma prévia fora do site/

O que você edita fica em conteudo/. Este arquivo é a máquina; normalmente
você não precisa abri-lo.
"""

from __future__ import annotations

import html
import json
import os
import re
import shutil
import sys
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote as url_quote

RAIZ = Path(__file__).resolve().parent
CONTEUDO = RAIZ / "conteudo"
TEMA = RAIZ / "tema"

try:
    from PIL import Image as _PILImage
except ImportError:  # Pillow é opcional: sem ela caímos de volta nas dimensões-padrão.
    _PILImage = None

# cache de dimensões reais de imagem, por caminho absoluto -> (largura, altura).
# Evita reabrir o mesmo arquivo várias vezes (capa de card + galeria + og:image
# costumam repetir a mesma foto).
_DIMENSOES_CACHE: dict[Path, tuple[int, int]] = {}


def dimensoes_imagem(caminho_absoluto: Path, largura_padrao: int, altura_padrao: int) -> tuple[int, int]:
    """Le a dimensao real de um arquivo de imagem com Pillow.

    Usado para gravar width/height corretos em cada <img> (evita layout shift
    e é considerado pelo Google em Core Web Vitals). Se o Pillow não estiver
    instalado, ou o arquivo não existir/não puder ser lido, devolve o
    width/height padrão passado pelo chamador — o build nunca quebra por causa
    disso, só perde a precisão da dimensão.
    """
    if _PILImage is None:
        return largura_padrao, altura_padrao
    if caminho_absoluto in _DIMENSOES_CACHE:
        return _DIMENSOES_CACHE[caminho_absoluto]
    try:
        with _PILImage.open(caminho_absoluto) as img:
            dim = (img.width, img.height)
    except Exception:
        dim = (largura_padrao, altura_padrao)
    _DIMENSOES_CACHE[caminho_absoluto] = dim
    return dim


_NUMERAIS_ROMANOS = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
                     "XI", "XII"]


def numeral_romano(n: int) -> str:
    """Numeral romano para os cartoes de pilares/servicos (I, II, III...) -
    troca o "01/02/03/04" de template generico por algo com mais cara de
    marca. Cai de volta para o numero arabico se passar de 12 (nao deveria
    acontecer com o conteudo atual, mas evita indice fora da lista)."""
    if 1 <= n <= len(_NUMERAIS_ROMANOS):
        return _NUMERAIS_ROMANOS[n - 1]
    return str(n)


def dimensoes_midia_url(url_publica: str, largura_padrao: int, altura_padrao: int) -> tuple[int, int]:
    """Mesma coisa que dimensoes_imagem, mas a partir de uma URL pública
    (ex.: "/midia/imoveis/fazenda-x/foto-01.jpg") — resolve para o arquivo
    correspondente dentro de conteudo/midia/."""
    if not url_publica.startswith("/midia/"):
        return largura_padrao, altura_padrao
    caminho = CONTEUDO / "midia" / url_publica[len("/midia/"):].lstrip("/")
    return dimensoes_imagem(caminho, largura_padrao, altura_padrao)


def _saida_padrao() -> Path:
    if "--saida" in sys.argv:
        i = sys.argv.index("--saida")
        if i + 1 >= len(sys.argv) or sys.argv[i + 1].startswith("--"):
            bloqueio("--saida exige um caminho logo depois dela.")
            return RAIZ / "site"
        return Path(sys.argv[i + 1]).expanduser()
    return RAIZ / "site"


SAIDA = _saida_padrao()

PENDENTE = "PREENCHER"

# --demo mostra tambem o que esta com publicado=false, para conferir o layout
# antes de gerar a saida final. O fluxo de publicacao sempre usa a versao
# normal, entao rascunho nao tem como escapar para o site.
MOSTRAR_RASCUNHOS = "--demo" in sys.argv

avisos: list[str] = []
bloqueios: list[str] = []


# ============================================================== utilidades ==

def aviso(msg: str) -> None:
    avisos.append(msg)


def bloqueio(msg: str) -> None:
    bloqueios.append(msg)


def ler_json(caminho: Path) -> dict:
    if not caminho.exists():
        bloqueio(f"arquivo obrigatório não encontrado: {caminho.relative_to(RAIZ)}")
        return {}
    try:
        # utf-8-sig, e nao utf-8: o Bloco de Notas e o PowerShell gravam UTF-8
        # com BOM, e o parser padrao rejeita esses 3 bytes com uma mensagem que
        # nao ajuda ninguem. Assim os dois formatos funcionam.
        with caminho.open(encoding="utf-8-sig") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        bloqueio(
            f"{caminho.relative_to(RAIZ)} tem erro de JSON na linha {e.lineno}, "
            f"coluna {e.colno}: {e.msg}. Provavelmente falta uma vírgula, "
            f"sobra uma vírgula no fim de uma lista, ou uma aspa não foi fechada."
        )
        return {}


def e(texto) -> str:
    """Escapa para uso seguro em HTML."""
    if texto is None:
        return ""
    return html.escape(str(texto), quote=True)


def preenchido(valor) -> bool:
    if valor is None:
        return False
    v = str(valor).strip()
    return bool(v) and v != PENDENTE


def limpar_meta(d: dict) -> dict:
    """Remove as chaves de anotação (que começam com _)."""
    return {k: v for k, v in d.items() if not k.startswith("_")}


def paragrafos(valor) -> str:
    """Aceita string (com \\n\\n) ou lista de strings e devolve <p>...</p>."""
    if not valor:
        return ""
    if isinstance(valor, str):
        blocos = [b.strip() for b in valor.split("\n\n") if b.strip()]
    else:
        blocos = [str(b).strip() for b in valor if str(b).strip()]
    return "\n".join(f"<p>{e(b)}</p>" for b in blocos)


def fmt_num(n) -> str:
    try:
        n = float(n)
    except (TypeError, ValueError):
        return ""
    if n == int(n):
        return f"{int(n):,}".replace(",", ".")
    return f"{n:,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def fmt_reais(valor) -> str:
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return ""
    if v <= 0:
        return ""
    if v >= 1_000_000:
        milhoes = v / 1_000_000
        texto = f"{milhoes:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
        texto = texto.replace(",0", "")
        return f"R$ {texto} mi"
    return "R$ " + fmt_num(round(v))


def fmt_dolar(valor_reais, taxa) -> str:
    """Converte um valor em reais para dolar usando uma taxa fixa (cambio referencial,
    nao uma cotacao ao vivo) e formata no mesmo estilo de fmt_reais."""
    try:
        v = float(valor_reais)
        taxa = float(taxa)
    except (TypeError, ValueError):
        return ""
    if v <= 0 or taxa <= 0:
        return ""
    usd = v / taxa
    if usd >= 1_000_000:
        milhoes = usd / 1_000_000
        texto = f"{milhoes:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
        texto = texto.replace(",0", "")
        return f"US$ {texto} mi"
    return "US$ " + fmt_num(round(usd))


def preco_usd_html(valor, cambio, classe="dado__val-usd") -> str:
    """Span pequeno com o valor aproximado em dolar, ao lado do preco em reais.
    Retorna vazio se nao houver taxa de cambio configurada em conteudo/config.json."""
    taxa = (cambio or {}).get("usd_brl")
    if not (valor and taxa):
        return ""
    txt = fmt_dolar(valor, taxa)
    if not txt:
        return ""
    return " " + '<small class="' + classe + '">&asymp; ' + e(txt) + '</small>'


def nota_cambio_html(cambio, lang="pt") -> str:
    """Aviso de que o valor em dolar usa cambio fixo/referencial, nao uma API ao vivo."""
    if not cambio or not cambio.get("usd_brl"):
        return ""
    taxa_fmt = fmt_num(cambio["usd_brl"])
    data_fmt = cambio.get("atualizado_em", "")
    if data_fmt:
        try:
            data_fmt = fmt_data(date.fromisoformat(data_fmt))
        except ValueError:
            pass
    if lang == "en":
        texto = "Reference exchange rate: US$ 1 = R$ " + taxa_fmt
        if data_fmt:
            texto += " (" + data_fmt + ")"
        texto += ". The dollar amount is approximate."
    elif lang == "zh":
        texto = "参考汇率：1美元 = " + taxa_fmt + " 雷亚尔"
        if data_fmt:
            texto += "（" + data_fmt + "）"
        texto += "。美元金额为约值。"
    else:
        texto = "Câmbio referencial: US$ 1 = R$ " + taxa_fmt
        if data_fmt:
            texto += " (" + data_fmt + ")"
        texto += ". O valor em dólar é aproximado."
    return '<p class="painel__preco-cambio">' + e(texto) + '</p>'



def resumo_fator_regiao(texto: str, indice: int, lang: str = "pt") -> tuple[str, str]:
    """Transforma a lista bruta de fatores regionais em titulo + resumo curto."""
    texto = str(texto).strip().rstrip(".")
    mapa = {
        "Logística conectada aos corredores Norte e ao Arco Norte": (
            "Logística",
            "Conexão com os corredores Norte e com a saída mais estratégica da produção.",
        ),
        "Solo e clima com aptidão para soja, milho, algodão e pecuária": (
            "Aptidão produtiva",
            "Base técnica forte para grãos, fibras e pecuária em escala.",
        ),
        "Custo por hectare ainda abaixo das regiões consolidadas do Centro-Sul": (
            "Preço de entrada",
            "Ainda há janela de aquisição abaixo das praças já totalmente consolidadas.",
        ),
        "Base tecnológica e serviços agrícolas em expansão": (
            "Ecossistema",
            "A oferta de tecnologia, insumos e suporte técnico amadureceu muito na região.",
        ),
        "Disponibilidade hídrica e potencial de irrigação": (
            "Água",
            "A leitura hídrica continua sendo peça central para produtividade e valorização.",
        ),
    }
    mapa_en = {
        "Logistics connected to the Northern corridors and the Arco Norte": (
            "Logistics", "Connection to the Northern corridors and the most strategic outlet for production."),
        "Soil and climate suited to soybeans, corn, cotton and cattle ranching": (
            "Production fitness", "Strong technical base for grains, fiber crops and cattle ranching at scale."),
        "Cost per hectare still below the consolidated Center-South regions": (
            "Entry price", "There is still an acquisition window below the already fully consolidated markets."),
        "Growing technology base and agricultural services": (
            "Ecosystem", "The supply of technology, inputs and technical support has matured a lot in the region."),
        "Water availability and irrigation potential": (
            "Water", "Water availability remains a central factor for productivity and appreciation."),
    }
    mapa_zh = {
        "物流连接北方走廊及北方弧线（Arco Norte）": ("物流", "连接北方走廊及最具战略意义的农产品出口通道。"),
        "土壤与气候适宜种植大豆、玉米、棉花及发展畜牧业": ("生产适宜性", "为规模化的谷物、纤维作物及畜牧业提供强大的技术基础。"),
        "每公顷成本仍低于已整合的中南部地区": ("进入价格", "相较于已完全整合的市场,仍存在较低成本的购入窗口。"),
        "技术基础与农业服务体系不断扩展": ("生态体系", "该地区的技术、投入品及技术支持供给已大幅成熟。"),
        "水资源可用性及灌溉潜力": ("水资源", "水资源可用性仍是生产力与增值的核心因素。"),
    }
    if lang == "en" and texto in mapa_en:
        return mapa_en[texto]
    if lang == "zh" and texto in mapa_zh:
        return mapa_zh[texto]
    if texto in mapa:
        return mapa[texto]

    partes = texto.split()
    titulo = " ".join(partes[:2]).strip() if len(partes) >= 2 else texto[:24].strip()
    if not titulo:
        titulo = f"Item {indice:02d}"
    return titulo, texto


MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]


def fmt_data(d: date) -> str:
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def fmt_intervalo(data_inicio: date, data_fim: date | None) -> str:
    """Formata um intervalo de datas de evento: '18 de agosto de 2026' ou
    '29 de agosto a 6 de setembro de 2026' (mesmo mes/ano some da 1a parte)."""
    if not data_fim or data_fim == data_inicio:
        return fmt_data(data_inicio)
    if data_inicio.year == data_fim.year and data_inicio.month == data_fim.month:
        return f"{data_inicio.day} a {data_fim.day} de {MESES[data_fim.month - 1]} de {data_fim.year}"
    if data_inicio.year == data_fim.year:
        return f"{data_inicio.day} de {MESES[data_inicio.month - 1]} a {fmt_data(data_fim)}"
    return f"{fmt_data(data_inicio)} a {fmt_data(data_fim)}"


TIPOS = {
    "agricola": "Agrícola",
    "pecuaria": "Pecuária",
    "mista": "Mista",
    "reflorestamento": "Reflorestamento",
    "lazer": "Lazer",
}

STATUS = {
    "disponivel": ("Disponível", "selo--azul"),
    "reservado": ("Reservado", "selo--dourado"),
    "vendido": ("Vendido", "selo--vendido"),
}


def slugificar(texto: str) -> str:
    t = str(texto).lower().strip()
    acentos = {"á": "a", "à": "a", "â": "a", "ã": "a", "ä": "a", "é": "e", "ê": "e",
               "è": "e", "í": "i", "ì": "i", "ó": "o", "ô": "o", "õ": "o", "ò": "o",
               "ú": "u", "ù": "u", "û": "u", "ü": "u", "ç": "c", "ñ": "n"}
    for a, b in acentos.items():
        t = t.replace(a, b)
    t = re.sub(r"[^a-z0-9]+", "-", t)
    return t.strip("-")


# ================================================= markdown minimalista ====

def md_inline(t: str) -> str:
    t = e(t)
    t = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    return t


def markdown(texto: str) -> str:
    """Subconjunto de Markdown: h2-h4, listas, citação, parágrafo, hr."""
    linhas = texto.replace("\r\n", "\n").split("\n")
    saida: list[str] = []
    buffer_p: list[str] = []
    lista: list[str] = []
    tipo_lista = None
    citacao: list[str] = []
    tabela: list[str] = []

    def fecha_p():
        nonlocal buffer_p
        if buffer_p:
            saida.append("<p>" + md_inline(" ".join(buffer_p)) + "</p>")
            buffer_p = []

    def fecha_lista():
        nonlocal lista, tipo_lista
        if lista:
            tag = tipo_lista or "ul"
            itens = "".join(f"<li>{md_inline(i)}</li>" for i in lista)
            saida.append(f"<{tag}>{itens}</{tag}>")
            lista = []
            tipo_lista = None

    def fecha_citacao():
        nonlocal citacao
        if citacao:
            saida.append("<blockquote>" + md_inline(" ".join(citacao)) + "</blockquote>")
            citacao = []

    def fecha_tabela():
        nonlocal tabela
        if not tabela:
            return
        linhas_tab = [l for l in tabela if not re.match(r"^\s*\|?[\s:|-]+\|?\s*$", l)]
        if linhas_tab:
            def celulas(linha):
                bruto = linha.strip()
                if bruto.startswith("|"):
                    bruto = bruto[1:]
                if bruto.endswith("|"):
                    bruto = bruto[:-1]
                return [c.strip() for c in bruto.split("|")]

            cabecalho = celulas(linhas_tab[0])
            corpo = [celulas(l) for l in linhas_tab[1:]]
            th = "".join(f"<th>{md_inline(c)}</th>" for c in cabecalho)
            trs = "".join(
                "<tr>" + "".join(f"<td>{md_inline(c)}</td>" for c in linha) + "</tr>"
                for linha in corpo
            )
            saida.append(
                '<div class="tabela-rolavel"><table><thead><tr>'
                + th + "</tr></thead><tbody>" + trs + "</tbody></table></div>"
            )
        tabela = []

    def fecha_tudo():
        fecha_p()
        fecha_lista()
        fecha_citacao()
        fecha_tabela()

    for linha in linhas:
        crua = linha.rstrip()
        strip = crua.strip()

        if not strip:
            fecha_tudo()
            continue

        # linha de tabela: comeca e termina com | e tem ao menos duas colunas
        if strip.startswith("|") and strip.endswith("|") and strip.count("|") >= 3:
            fecha_p()
            fecha_lista()
            fecha_citacao()
            tabela.append(strip)
            continue

        m = re.match(r"^(#{2,4})\s+(.*)$", strip)
        if m:
            fecha_tudo()
            nivel = len(m.group(1))
            saida.append(f"<h{nivel}>{md_inline(m.group(2))}</h{nivel}>")
            continue

        if strip in ("---", "***", "___"):
            fecha_tudo()
            saida.append("<hr>")
            continue

        if strip.startswith("> "):
            fecha_p()
            fecha_lista()
            citacao.append(strip[2:])
            continue

        m = re.match(r"^[-*+]\s+(.*)$", strip)
        if m:
            fecha_p()
            fecha_citacao()
            if tipo_lista == "ol":
                fecha_lista()
            tipo_lista = "ul"
            lista.append(m.group(1))
            continue

        m = re.match(r"^\d+[.)]\s+(.*)$", strip)
        if m:
            fecha_p()
            fecha_citacao()
            if tipo_lista == "ul":
                fecha_lista()
            tipo_lista = "ol"
            lista.append(m.group(1))
            continue

        fecha_lista()
        fecha_citacao()
        buffer_p.append(strip)

    fecha_tudo()
    return "\n".join(saida)


def ler_markdown_com_frontmatter(caminho: Path) -> tuple[dict, str]:
    bruto = caminho.read_text(encoding="utf-8")
    meta: dict = {}
    corpo = bruto

    if bruto.lstrip().startswith("---"):
        bruto = bruto.lstrip()
        partes = bruto.split("---", 2)
        if len(partes) >= 3:
            cabecalho, corpo = partes[1], partes[2]
            for linha in cabecalho.strip().split("\n"):
                if ":" not in linha:
                    continue
                chave, _, valor = linha.partition(":")
                chave = chave.strip()
                valor = valor.strip().strip('"').strip("'")
                if valor.lower() in ("true", "false"):
                    meta[chave] = valor.lower() == "true"
                else:
                    meta[chave] = valor
    return meta, corpo.strip()


# ========================================================== peças visuais ==

SVG_HORIZONTE = (
    '<svg class="hero__horizonte" viewBox="0 0 1440 220" preserveAspectRatio="none" '
    'aria-hidden="true" focusable="false" height="220">'
    '<path fill="#0C1E33" fill-opacity=".55" d="M0 168l120-26 110 18 130-40 140 30 120-24 '
    '130 34 140-30 120 22 110-18 120 26v66H0z"/>'
    '<path fill="#0C1E33" fill-opacity=".85" d="M0 196l160-20 140 16 150-26 130 22 140-18 '
    '160 24 140-16 160 20v34H0z"/>'
    "</svg>"
)

SVG_CAPA = (
    '<svg viewBox="0 0 800 200" preserveAspectRatio="none" aria-hidden="true" '
    'focusable="false" height="200">'
    '<path fill="#0C1E33" fill-opacity=".5" d="M0 128l90-22 80 16 100-32 90 24 100-20 '
    '90 26 90-22 80 18 80-16v100H0z"/>'
    '<path fill="#0C1E33" fill-opacity=".8" d="M0 158l110-16 90 12 110-20 100 16 '
    '110-14 100 18 90-12 90 16v42H0z"/>'
    "</svg>"
)

# Ícones de linha (estilo Lucide/Feather), inline e minimalistas — usados nos
# cards "Por que a Prime" (pilares) na home. currentColor herda a cor definida
# em .card__icone, sem depender de imagem externa ou emoji.
ICONES_PILARES = [
    # 01 · Documentação verificada — escudo com check: símbolo universal de
    # segurança/verificação, mais forte e imediato que uma medalha.
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">'
    '<path d="M12 3.2l6.8 2.5v5.4c0 4.55-2.9 8.2-6.8 9.7-3.9-1.5-6.8-5.15-6.8-9.7V5.7z"/>'
    '<path d="M8.6 12.15l2.35 2.35 4.45-4.8"/></svg>',
    # 02 · Consultoria do início ao fim — maleta: acompanhamento
    # profissional e assessoria direta, símbolo limpo e inconfundível
    # em tamanho pequeno (o aperto de mãos não se sustentava a 24px).
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">'
    '<rect x="3.2" y="8.4" width="17.6" height="11.2" rx="1.8"/>'
    '<path d="M8.6 8.4V6.6a1.8 1.8 0 0 1 1.8-1.8h3.2a1.8 1.8 0 0 1 1.8 1.8v1.8"/>'
    '<path d="M3.2 13.4h17.6"/>'
    '<path d="M10.6 13.4v1.5h2.8v-1.5" stroke-linejoin="round"/></svg>',
    # 03 · Rede nacional e internacional — globo com meridianos/paralelos e
    # pontos conectados por linhas finas, reforçando "rede" além de "mundo".
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">'
    '<circle cx="12" cy="12" r="9"/>'
    '<ellipse cx="12" cy="12" rx="4" ry="9"/>'
    '<path d="M3 12h18"/>'
    '<path stroke-width="1.3" d="M7.9 7.8l4.5 3.4 4.1-2.9M12.4 11.2l1.5 5.3"/>'
    '<circle cx="7.9" cy="7.8" r="1.15" fill="currentColor" stroke="none"/>'
    '<circle cx="16.5" cy="8.3" r="1.15" fill="currentColor" stroke="none"/>'
    '<circle cx="13.9" cy="17.1" r="1.15" fill="currentColor" stroke="none"/></svg>',
    # 04 · Conhecimento de região — bússola/rosa dos ventos com os 4 pontos
    # cardeais marcados: territorial e específico, mais elegante que um mapa.
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">'
    '<circle cx="12" cy="12" r="9"/>'
    '<path stroke-linecap="butt" d="M12 1.5v2.3M12 20.2v2.3M1.5 12h2.3M20.2 12h2.3"/>'
    '<path d="M12 5.9l2.35 5.55c.13.3.13.6 0 .9L12 18.1l-2.35-5.75c-.13-.3-.13-.6 0-.9z" '
    'fill="currentColor" stroke-linejoin="round"/></svg>',
]

# Marca da Prime Fazendas: sol sobre os sulcos do plantio.
# O desenho vem de tema/assets/marca.svg, gerado por ferramentas/gerar_og.py a
# partir da mesma geometria da imagem de compartilhamento — logo do site e
# miniatura do WhatsApp sao o mesmo desenho, nunca divergem.
_MARCA_SVG = (TEMA / "assets" / "marca.svg").read_text(encoding="utf-8")     if (TEMA / "assets" / "marca.svg").exists() else ""

if not _MARCA_SVG:
    aviso("tema/assets/marca.svg nao encontrado — rode: python ferramentas/gerar_og.py")


def svg_marca(classe: str = "marca__selo", tam: int = 40, ident: str = "pf") -> str:
    """Insere a marca com um id de mascara proprio, para poder repetir na pagina."""
    if not _MARCA_SVG:
        return ""
    svg = _MARCA_SVG.replace("MASCARA", f"{ident}-sulcos")
    return svg.replace(
        "<svg ",
        f'<svg class="{classe}" width="{tam}" height="{tam}" '
        f'aria-hidden="true" focusable="false" ',
        1,
    )


SVG_SELO = '<span class="marca__disco"><img class="marca__selo" src="/assets/logo.png" width="40" height="40" alt="" loading="eager"></span>'
SVG_SELO_RODAPE = '<span class="marca__disco"><img class="marca__selo" src="/assets/logo.png" width="40" height="40" alt="" loading="lazy"></span>'

ICONES_REDE = {
    "instagram": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2.16c3.2 0 3.58.01 4.85.07 1.17.05 1.96.24 2.65.51.72.28 1.33.66 1.94 1.27.61.61.99 1.22 1.27 1.94.27.69.46 1.48.51 2.65.06 1.27.07 1.65.07 4.85s-.01 3.58-.07 4.85c-.05 1.17-.24 1.96-.51 2.65a5.2 5.2 0 0 1-1.27 1.94 5.2 5.2 0 0 1-1.94 1.27c-.69.27-1.48.46-2.65.51-1.27.06-1.65.07-4.85.07s-3.58-.01-4.85-.07c-1.17-.05-1.96-.24-2.65-.51a5.2 5.2 0 0 1-1.94-1.27 5.2 5.2 0 0 1-1.27-1.94c-.27-.69-.46-1.48-.51-2.65C2.17 15.58 2.16 15.2 2.16 12s.01-3.58.07-4.85c.05-1.17.24-1.96.51-2.65.28-.72.66-1.33 1.27-1.94A5.2 5.2 0 0 1 5.95 1.3c.69-.27 1.48-.46 2.65-.51C9.87 2.17 10.25 2.16 12 2.16zm0 1.98c-3.15 0-3.5.01-4.74.07-.95.04-1.47.2-1.81.34-.46.18-.78.39-1.13.74-.35.35-.56.67-.74 1.13-.14.34-.3.86-.34 1.81-.06 1.24-.07 1.59-.07 4.74s.01 3.5.07 4.74c.04.95.2 1.47.34 1.81.18.46.39.78.74 1.13.35.35.67.56 1.13.74.34.14.86.3 1.81.34 1.24.06 1.59.07 4.74.07s3.5-.01 4.74-.07c.95-.04 1.47-.2 1.81-.34.46-.18.78-.39 1.13-.74.35-.35.56-.67.74-1.13.14-.34.3-.86.34-1.81.06-1.24.07-1.59.07-4.74s-.01-3.5-.07-4.74c-.04-.95-.2-1.47-.34-1.81a3.2 3.2 0 0 0-.74-1.13 3.2 3.2 0 0 0-1.13-.74c-.34-.14-.86-.3-1.81-.34-1.24-.06-1.59-.07-4.74-.07zm0 3.37a4.49 4.49 0 1 1 0 8.98 4.49 4.49 0 0 1 0-8.98zm0 7.4a2.91 2.91 0 1 0 0-5.82 2.91 2.91 0 0 0 0 5.82zm5.72-7.6a1.05 1.05 0 1 1-2.1 0 1.05 1.05 0 0 1 2.1 0z"/></svg>',
    "linkedin": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6.94 5a1.94 1.94 0 1 1-3.88 0 1.94 1.94 0 0 1 3.88 0zM3.13 8.44h3.62V21H3.13V8.44zm5.94 0h3.47v1.72h.05a3.8 3.8 0 0 1 3.42-1.88c3.66 0 4.33 2.41 4.33 5.54V21h-3.62v-6.19c0-1.47-.03-3.37-2.05-3.37-2.06 0-2.37 1.6-2.37 3.26V21H9.07V8.44z"/></svg>',
    "youtube": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21.58 7.19a2.51 2.51 0 0 0-1.77-1.77C18.25 5 12 5 12 5s-6.25 0-7.81.42A2.51 2.51 0 0 0 2.42 7.2C2 8.75 2 12 2 12s0 3.25.42 4.81a2.51 2.51 0 0 0 1.77 1.77C5.75 19 12 19 12 19s6.25 0 7.81-.42a2.51 2.51 0 0 0 1.77-1.77C22 15.25 22 12 22 12s0-3.25-.42-4.81zM9.96 15.02V8.98L15.2 12l-5.23 3.02z"/></svg>',
    "facebook": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M22 12.06C22 6.5 17.52 2 12 2S2 6.5 2 12.06c0 5.02 3.66 9.18 8.44 9.94v-7.03H7.9v-2.91h2.54V9.85c0-2.51 1.49-3.9 3.77-3.9 1.1 0 2.24.2 2.24.2v2.46h-1.26c-1.24 0-1.63.78-1.63 1.57v1.88h2.78l-.45 2.91h-2.33V22c4.78-.76 8.44-4.92 8.44-9.94z"/></svg>',
}

SVG_ZAP = ('<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M17.47 14.38c-.3-.15-1.75-.86-2.02-.96-.27-.1-.47-.15-.67.15-.2.3-.77.96-.94 1.16-.17.2-.35.22-.64.07-.3-.15-1.11-.41-2.12-1.31-.78-.7-1.3-1.56-1.45-1.86-.15-.3-.02-.46.13-.61.13-.13.3-.35.44-.52.15-.17.2-.3.3-.5.1-.2.05-.37-.02-.52-.07-.15-.67-1.61-.92-2.2-.24-.58-.49-.5-.67-.51h-.57c-.2 0-.52.07-.79.37-.27.3-1.03 1.01-1.03 2.46 0 1.45 1.06 2.85 1.2 3.05.15.2 2.05 3.13 4.96 4.28.69.3 1.24.48 1.66.61.7.22 1.34.19 1.84.12.56-.08 1.75-.71 2-1.4.24-.69.24-1.28.17-1.4-.07-.13-.27-.2-.57-.35zM12.04 21.5h-.01c-1.73 0-3.43-.46-4.92-1.34l-.35-.21-3.66.96.98-3.57-.23-.37a9.4 9.4 0 0 1-1.44-5.02c0-5.21 4.25-9.45 9.47-9.45 2.53 0 4.9.99 6.69 2.77a9.38 9.38 0 0 1 2.77 6.69c0 5.21-4.25 9.45-9.47 9.45zM20.5 3.49A11.36 11.36 0 0 0 12.04 0C5.76 0 .65 5.1.65 11.38c0 2 .52 3.95 1.51 5.67L.5 24l7.1-1.86a11.34 11.34 0 0 0 4.44.9h.01c6.27 0 11.38-5.1 11.38-11.38 0-3.04-1.18-5.9-3.33-8.05z"/></svg>')


# ================================================================ layout ===

def montar_url_zap(cfg: dict, mensagem: str | None = None) -> str:
    numero = cfg["contato"].get("whatsapp_numero_internacional")
    if not preenchido(numero):
        return ""
    numero = re.sub(r"\D", "", str(numero))
    msg = mensagem or cfg["contato"].get("whatsapp_mensagem") or ""
    from urllib.parse import quote
    return f"https://wa.me/{numero}?text={quote(msg)}"


def formatar_telefone_exibicao(contato: dict, idioma: str = "") -> str:
    bruto = str(contato.get("telefone_link") or contato.get("telefone") or "").strip()
    if not bruto:
        return ""
    digitos = re.sub(r"\D", "", bruto)
    if digitos.startswith("55") and len(digitos) >= 13:
        digitos = digitos[2:]
    if len(digitos) >= 10:
        ddd = digitos[:2]
        resto = digitos[2:]
        if len(resto) >= 9:
            local = f"{ddd}-{resto[:5]}-{resto[5:9]}"
        elif len(resto) >= 8:
            local = f"{ddd}-{resto[:4]}-{resto[4:8]}"
        else:
            local = f"{ddd}-{resto}"
    else:
        local = contato.get("telefone", bruto)
    if str(idioma).lower().startswith("en"):
        return f"+55 {local}" if local else contato.get("telefone", bruto)
    return local


PAGINAS_TRADUZIDAS = {
    "/": {"en": "/en/", "zh": "/zh/"},
    "/sobre/": {"en": "/en/sobre/", "zh": "/zh/sobre/"},
    "/servicos/": {"en": "/en/servicos/", "zh": "/zh/servicos/"},
    "/data-center/": {"en": "/en/data-center/", "zh": "/zh/data-center/"},
    "/contato/": {"en": "/en/contato/", "zh": "/zh/contato/"},
    "/agenda-agro/": {"en": "/en/agenda-agro/", "zh": "/zh/agenda-agro/"},
    "/imoveis/": {"en": "/en/imoveis/", "zh": "/zh/imoveis/"},
    "/blog/": {"en": "/en/blog/", "zh": "/zh/blog/"},
    "/investir-no-agro/": {"en": "/en/investir-no-agro/", "zh": "/zh/investir-no-agro/"},
}


def hreflang_para(cfg: dict, url_pt: str) -> list[tuple[str, str]] | None:
    """Monta a lista de tags hreflang (pt-BR/en/zh-Hans/x-default) para uma
    URL em portugues que tenha traducao registrada em PAGINAS_TRADUZIDAS.
    Retorna None se a pagina nao tiver versao traduzida (nesse caso nenhuma
    tag hreflang deve ser emitida, pois nao ha reciprocidade possivel)."""
    trad = PAGINAS_TRADUZIDAS.get(url_pt)
    if not trad:
        return None
    dominio = cfg["site"]["dominio"].rstrip("/")
    return [
        ("pt-BR", f"{dominio}{url_pt}"),
        ("en", f"{dominio}{trad['en']}"),
        ("zh-Hans", f"{dominio}{trad['zh']}"),
        ("x-default", f"{dominio}{url_pt}"),
    ]


def registrar_imoveis_traduzidos(imoveis: list[dict], trad_map: dict) -> None:
    """Preenche PAGINAS_TRADUZIDAS com a URL de cada ficha de imovel que tenha
    traducao disponivel em conteudo/imoveis_i18n.json, para que o seletor de
    idioma no topo funcione tambem dentro da ficha de cada fazenda."""
    for im in imoveis:
        if im["slug"] in trad_map:
            PAGINAS_TRADUZIDAS[im["url"]] = {
                "en": f"/en/imoveis/{im['slug']}/",
                "zh": f"/zh/imoveis/{im['slug']}/",
            }

BANDEIRA_SVG = {
    "pt": '<svg viewBox="0 0 24 16" aria-hidden="true"><rect width="24" height="16" fill="#009739"/><path d="M12 2 22 8 12 14 2 8Z" fill="#FEDD00"/><circle cx="12" cy="8" r="3.2" fill="#012169"/></svg>',
    "en": '<svg viewBox="0 0 24 16" aria-hidden="true"><rect width="24" height="16" fill="#B22234"/><rect width="24" height="1.23" y="1.23" fill="#fff"/><rect width="24" height="1.23" y="3.69" fill="#fff"/><rect width="24" height="1.23" y="6.15" fill="#fff"/><rect width="24" height="1.23" y="8.62" fill="#fff"/><rect width="24" height="1.23" y="11.08" fill="#fff"/><rect width="24" height="1.23" y="13.54" fill="#fff"/><rect width="10" height="8.62" fill="#3C3B6E"/></svg>',
    "zh": '<svg viewBox="0 0 24 16" aria-hidden="true"><rect width="24" height="16" fill="#DE2910"/><path d="M4 3 4.9 5.7 2.4 4.1H5.6L3.1 5.7Z" fill="#FFDE00"/></svg>',
}


def seletor_idioma(pt_url: str | None, en_url: str | None, zh_url: str | None, atual: str) -> str:
    """Bandeirinhas de troca de idioma, canto superior direito do menu."""
    opcoes = [("pt", pt_url, "Português"), ("en", en_url, "English"), ("zh", zh_url, "中文")]
    itens = "".join(
        f'<a href="{e(url)}" class="idioma__opcao{" idioma__opcao--atual" if cod == atual else ""}" '
        f'title="{e(rotulo)}" aria-label="{e(rotulo)}">{BANDEIRA_SVG[cod]}</a>'
        for cod, url, rotulo in opcoes if url
    )
    return f'<div class="idioma-seletor">{itens}</div>'


def cabecalho(cfg: dict, url_atual: str) -> str:
    itens = []
    for item in cfg.get("navegacao", []):
        atual = ' aria-current="page"' if item["url"] == url_atual else ""
        itens.append(f'<a href="{e(item["url"])}"{atual}>{e(item["titulo"])}</a>')

    zap = montar_url_zap(cfg)
    cta_mobile = ""
    if zap:
        cta_mobile = f'<a class="btn btn--principal btn--bloco" href="{e(zap)}" target="_blank" rel="noopener">{SVG_ZAP}Falar no WhatsApp</a>'

    cta_topo = (
        f'<a class="btn btn--principal" href="{e(zap)}" target="_blank" rel="noopener">{SVG_ZAP}Falar no WhatsApp</a>'
        if zap else
        '<a class="btn btn--principal" href="/contato/">Fale com um especialista</a>'
    )

    trad = PAGINAS_TRADUZIDAS.get(url_atual, {})
    seletor = seletor_idioma(url_atual, trad.get("en") or "/en/", trad.get("zh") or "/zh/", "pt")

    return f"""<header class="topo">
  <div class="env topo__int">
    <a class="marca" href="/" aria-label="{e(cfg['marca']['nome'])} — página inicial">
      {SVG_SELO}
      <span class="marca__txt">
        <span class="marca__nome">{e(cfg['marca']['nome'])}</span>
        <span class="marca__sub">Imóveis Rurais</span>
      </span>
    </a>
    <nav class="nav" id="nav-principal" aria-label="Navegação principal">
      {''.join(itens)}
      {cta_mobile}
    </nav>
    <div class="topo__acao">
      {seletor}
      {cta_topo}
      <button class="hamburguer" type="button" aria-expanded="false"
              aria-controls="nav-principal" aria-label="Abrir menu"><span></span></button>
    </div>
  </div>
</header>"""


def rodape(cfg: dict) -> str:
    nav = "".join(
        f'<li><a href="{e(i["url"])}">{e(i["titulo"])}</a></li>'
        for i in cfg.get("navegacao", [])
    )

    redes = ""
    for rede, url in cfg.get("redes", {}).items():
        if preenchido(url) and rede in ICONES_REDE:
            redes += (f'<a href="{e(url)}" target="_blank" rel="noopener me" '
                      f'aria-label="{rede.capitalize()}">{ICONES_REDE[rede]}</a>')
    if redes:
        redes = f'<div class="redes">{redes}</div>'

    c = cfg["contato"]
    linhas = []
    if preenchido(c.get("telefone")):
        tel = re.sub(r"\D", "", c.get("telefone_link") or c["telefone"])
        linhas.append(f'<li><a href="tel:+{tel}">{e(formatar_telefone_exibicao(c, cfg.get("site", {}).get("idioma", "")))}</a></li>')
    if preenchido(c.get("email")):
        linhas.append(f'<li><a href="mailto:{e(c["email"])}">{e(c["email"])}</a></li>')
    if preenchido(c.get("endereco")):
        linhas.append(f'<li>{e(c["endereco"])}</li>')
    cidade = ", ".join(x for x in [c.get("cidade"), c.get("estado")] if preenchido(x))
    if cidade:
        linhas.append(f"<li>{e(cidade)}</li>")
    if preenchido(c.get("creci")):
        linhas.append(f'<li>CRECI {e(c["creci"])}</li>')

    rod = cfg.get("rodape", {})
    legal = rod.get("aviso_legal", "")

    return f"""<footer class="rodape">
  <div class="env">
    <div class="rodape__grade">
      <div>
        <a class="marca" href="/" aria-label="{e(cfg['marca']['nome'])}">
          {SVG_SELO_RODAPE}
          <span class="marca__txt"><span class="marca__nome">{e(cfg['marca']['nome'])}</span>
          <span class="marca__sub">Imóveis Rurais</span></span>
        </a>
        {f'<p class="rodape__tagline">{e(cfg["marca"]["tagline"])}</p>' if preenchido(cfg['marca'].get('tagline')) else ''}
        <p class="rodape__sobre">{e(rod.get('sobre_curto', ''))}</p>
        {redes}
      </div>
      <div>
        <h4>Navegação</h4>
        <ul class="rodape__lista">{nav}</ul>
      </div>
      <div>
        <h4>Contato</h4>
        <ul class="rodape__lista">{''.join(linhas) or '<li>Em atualização</li>'}</ul>
      </div>
      <div>
        <h4>{e(cfg.get('comunidade', {}).get('nome', 'Comunidade'))}</h4>
        <ul class="rodape__lista">
          <li><a href="/blog/">Entrar na comunidade</a></li>
          <li><a href="/blog/">Notícias e insights</a></li>
          <li><a href="/imoveis/">Imóveis à venda</a></li>
        </ul>
      </div>
    </div>
    <div class="rodape__base">
      <span>&copy; <span data-ano>{date.today().year}</span> {e(cfg['marca']['nome'])}. Todos os direitos reservados.</span>
      <span>{e(cfg['contato'].get('horario', ''))}</span>
    </div>
    <p class="rodape__legal">{e(legal)}</p>
  </div>
</footer>"""


def pagina(cfg: dict, *, titulo: str, descricao: str, url: str, corpo: str,
           og_tipo: str = "website", json_ld: str | list[str] = "", rascunho: bool = False,
           og_imagem: str = "", hreflang: list[tuple[str, str]] | None = None,
           idioma: str = "", robots: str = "index, follow") -> str:
    site = cfg["site"]
    dominio = site["dominio"].rstrip("/")
    canonica = dominio + url
    titulo_completo = titulo if titulo == site["titulo_padrao"] else f"{titulo} | {cfg['marca']['nome']}"
    idioma_pagina = idioma or site.get("idioma", "pt-BR")
    hreflang_tags = ""
    if hreflang:
        hreflang_tags = "\n".join(
            f'<link rel="alternate" hreflang="{e(lng)}" href="{e(href)}">' for lng, href in hreflang
        )

    ga = ""
    if preenchido(cfg.get("analytics", {}).get("ga4_id")):
        gid = e(cfg["analytics"]["ga4_id"])
        ga = (f'<script async src="https://www.googletagmanager.com/gtag/js?id={gid}"></script>\n'
              f'<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}'
              f"gtag('js',new Date());gtag('config','{gid}');</script>")

    zap = montar_url_zap(cfg)
    botao_zap = ""
    if zap:
        botao_zap = (f'<a class="zap" href="{e(zap)}" target="_blank" rel="noopener" '
                     f'aria-label="Falar no WhatsApp">{SVG_ZAP}</a>')

    faixa = ""
    if rascunho:
        faixa = ('<div class="aviso-rascunho">Pré-visualização local — este conteúdo contém '
                 'dados de exemplo e não deve ir ao ar.</div>')

    blocos_ld = json_ld if isinstance(json_ld, list) else ([json_ld] if json_ld else [])
    ld = "\n".join(f'<script type="application/ld+json">{b}</script>' for b in blocos_ld if b)

    return f"""<!DOCTYPE html>
<html lang="{e(idioma_pagina)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(titulo_completo)}</title>
<meta name="description" content="{e(descricao)}">
<link rel="canonical" href="{e(canonica)}">
<meta name="robots" content="{e(robots)}">
{hreflang_tags}
<meta name="theme-color" content="#0C1E33">
<meta property="og:type" content="{e(og_tipo)}">
<meta property="og:site_name" content="{e(cfg['marca']['nome'])}">
<meta property="og:title" content="{e(titulo)}">
<meta property="og:description" content="{e(descricao)}">
<meta property="og:url" content="{e(canonica)}">
<meta property="og:locale" content="{e(idioma_pagina.replace("-","_"))}">
<meta property="og:image" content="{e(og_imagem or (dominio + site.get('og_imagem', '')))}">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="/assets/favicon-32.png" sizes="32x32" type="image/png">
<link rel="icon" href="/assets/favicon-192.png" sizes="192x192" type="image/png">
<link rel="apple-touch-icon" href="/assets/favicon-192.png">

<link rel="stylesheet" href="/assets/estilo.css">
{ld}
{ga}
<script defer src="/_vercel/insights/script.js"></script>
</head>
<body>
{faixa}
<a class="pular" href="#principal">Ir para o conteúdo</a>
{cabecalho(cfg, url)}
<main id="principal">
{corpo}
</main>
{rodape(cfg)}
{botao_zap}
<div class="foto-modal" hidden aria-hidden="true">
  <div class="foto-modal__janela" role="dialog" aria-modal="true" aria-label="Visualizador de imagem">
    <button type="button" class="foto-modal__fechar" aria-label="Fechar visualizador">×</button>
    <button type="button" class="foto-modal__nav foto-modal__anterior" aria-label="Foto anterior">‹</button>
    <img class="foto-modal__img" alt="">
    <button type="button" class="foto-modal__nav foto-modal__proximo" aria-label="Próxima foto">›</button>
    <p class="foto-modal__legenda"></p>
  </div>
</div>
<script src="/assets/site.js" defer></script>
</body>
</html>
"""


def hero(cfg: dict, *, olho: str, titulo: str, texto: str = "", botoes: str = "",
         interno: bool = False, foto: str = "") -> str:
    classe = "hero hero--interno" if interno else "hero"
    prioridade = ' fetchpriority="high"' if not interno else ''
    largura, altura = dimensoes_midia_url(foto, 1920, 1080) if foto else (1920, 1080)
    img = (f'<img class="hero__foto" src="{e(foto)}" alt="Paisagem rural de fazenda no Tocantins" '
           f'width="{largura}" height="{altura}" '
           f'loading="eager"{prioridade}>') if foto else ""
    return f"""<section class="{classe}">
  {img}{SVG_HORIZONTE}
  <div class="env hero__int">
    <p class="olho">{e(olho)}</p>
    <h1>{e(titulo)}</h1>
    {f'<p class="hero__texto">{e(texto)}</p>' if texto else ''}
    {f'<div class="grupo-btn">{botoes}</div>' if botoes else ''}
  </div>
</section>"""


def migalhas(trilha: list[tuple[str, str]]) -> str:
    partes = []
    for i, (rotulo, url) in enumerate(trilha):
        if i:
            partes.append("<span>/</span>")
        partes.append(f'<a href="{e(url)}">{e(rotulo)}</a>' if url else f"<span>{e(rotulo)}</span>")
    return f'<nav class="migalhas" aria-label="Trilha de navegação">{"".join(partes)}</nav>'


def ld_breadcrumbs(cfg: dict, trilha: list[tuple[str, str]]) -> str:
    """Gera o JSON-LD de BreadcrumbList (invisível, vai só no <head>) a partir
    da mesma trilha home > seção > página usada — ou equivalente — na
    migalha visual. Diferente da migalha visual, aqui toda posição precisa
    de uma URL (inclusive a página atual), porque é isso que o item.@id
    exige; o chamador deve passar a URL própria da página no último item."""
    dominio = cfg["site"]["dominio"].rstrip("/")
    itens = [
        {"@type": "ListItem", "position": i + 1, "name": nome, "item": dominio + url}
        for i, (nome, url) in enumerate(trilha)
    ]
    return json.dumps({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": itens,
    }, ensure_ascii=False)


def ld_breadcrumbs_i18n(cfg: dict, lang: str, trilha: list[tuple[str, str]]) -> str:
    """Mesma ideia de ld_breadcrumbs, para paginas EN/ZH: 'trilha' recebe pares
    (nome traduzido, caminho ja completo e correto), e a funcao so prefixa o
    item 'Home'/'首页' na frente. O caminho de itens dinamicos (ficha de imovel,
    post) deve vir pronto de im['url']/p['url'] (que ja cai pro PT quando nao
    ha traducao daquele item), nunca recalculado aqui."""
    home_label = {"en": "Home", "zh": "首页"}[lang]
    return ld_breadcrumbs(cfg, [(home_label, f"/{lang}/")] + trilha)


def descricao_foto(url_publica: str, titulo: str, local: str) -> str:
    """Alt text da foto de um imóvel. Quando o nome do arquivo dá uma pista
    razoável do conteúdo (ex.: 'aerea-02.jpg' — convenção usada pelo banco de
    mídia para vista aérea/drone), descreve isso; senão cai no padrão
    genérico título + local, que sempre está correto mesmo sem essa pista."""
    nome = url_publica.rsplit("/", 1)[-1].lower()
    base = f"{titulo} — {local}" if local else titulo
    if nome.startswith("aerea"):
        return f"Vista aérea — {base}"
    return base


def descricao_meta_imovel(im: dict) -> str:
    """Meta description dedicada por imóvel: combina região + área + um
    diferencial real (primeira característica/infraestrutura cadastrada),
    sem reaproveitar o texto do 'subtitulo' de tela. Ajustada para ficar
    entre 150 e 160 caracteres sempre que possível."""
    local = ", ".join(x for x in [im.get("municipio"), im.get("estado")] if preenchido(x))
    area = im.get("area_total_ha")
    tipo_label = TIPOS.get(im.get("tipo", ""), "")

    partes = []
    if area and local:
        partes.append(f"{fmt_num(area)} hectares em {local}")
    elif local:
        partes.append(local)
    elif area:
        partes.append(f"{fmt_num(area)} hectares")
    if tipo_label:
        partes.append(f"aptidão {tipo_label.lower()}")
    frase = ", ".join(partes)

    diferencial = ""
    for chave in ("caracteristicas", "infraestrutura"):
        itens = im.get(chave) or []
        if itens:
            diferencial = str(itens[0]).rstrip(".")
            break

    base = f"{im['titulo']}: {frase}." if frase else f"{im['titulo']}."

    def cortar(txt: str, limite: int) -> str:
        if len(txt) <= limite:
            return txt
        return txt[:limite].rsplit(" ", 1)[0].rstrip(".,;: ")

    # Monta com o diferencial e, se ainda houver espaço, um fechamento de
    # chamada — sempre cortando pelo componente MENOS essencial primeiro
    # (a chamada final, depois o diferencial), nunca no meio da frase.
    candidato = f"{base} {diferencial}." if diferencial else base
    fechamento = "Fale com a Prime Fazendas e confirme condições e disponibilidade."

    if len(candidato) < 150:
        com_fechamento = f"{candidato} {fechamento}"
        if len(com_fechamento) <= 160:
            return com_fechamento
        espaco = 160 - len(candidato) - 1
        if espaco > 20:
            return f"{candidato} {cortar(fechamento, espaco)}."
        return candidato

    if len(candidato) > 160:
        if diferencial:
            espaco_diferencial = 160 - len(base) - 2
            if espaco_diferencial > 20:
                return f"{base} {cortar(diferencial, espaco_diferencial)}."
            return cortar(base, 160)
        return cortar(candidato, 160)

    return candidato


def imoveis_relacionados(im: dict, todos: list[dict], maximo: int = 3) -> list[dict]:
    """Escolhe 2-3 fazendas 'relacionadas' para linkagem interna ao final da
    ficha: prioridade para o mesmo estado (UF); completa com a faixa de área
    mais próxima entre as demais, para nunca devolver menos que o possível."""
    candidatos = [
        o for o in todos
        if o["slug"] != im["slug"] and not o.get("_rascunho") and not o.get("_exemplo")
    ]
    area_alvo = im.get("area_total_ha") or 0

    def dist_area(o: dict) -> float:
        return abs((o.get("area_total_ha") or 0) - area_alvo)

    mesma_uf = sorted(
        (o for o in candidatos if o.get("estado") and o.get("estado") == im.get("estado")),
        key=dist_area,
    )
    escolhidos = mesma_uf[:maximo]
    if len(escolhidos) < maximo:
        restantes = sorted((o for o in candidatos if o not in escolhidos), key=dist_area)
        for o in restantes:
            if len(escolhidos) >= maximo:
                break
            escolhidos.append(o)
    return escolhidos


def cta_faixa(cfg: dict, titulo: str, texto: str, botao: str = "Falar com um especialista") -> str:
    zap = montar_url_zap(cfg)
    botoes = f'<a class="btn btn--dourado" href="/contato/">{e(botao)}</a>'
    if zap:
        botoes += f'<a class="btn btn--claro" href="{e(zap)}" target="_blank" rel="noopener">WhatsApp</a>'
    return f"""<section class="secao secao--compacta">
  <div class="env">
    <div class="cta-faixa">
      <h2>{e(titulo)}</h2>
      <p>{e(texto)}</p>
      <div class="grupo-btn">{botoes}</div>
    </div>
  </div>
</section>"""


def bloco_instagram(cfg: dict) -> str:
    url = cfg.get("redes", {}).get("instagram", "")
    if not preenchido(url):
        return ""
    handle = url.rstrip("/").rsplit("/", 1)[-1]
    return f"""<section class="secao secao--clara">
  <div class="env">
    <div class="instagram-faixa">
      <span class="instagram-faixa__icone">{ICONES_REDE['instagram']}</span>
      <div class="instagram-faixa__txt">
        <p class="olho">Bastidores e oportunidades</p>
        <h2>Acompanhe a Prime Fazendas no Instagram</h2>
        <p>Fotos, vídeos e novidades das propriedades direto de campo — @{e(handle)}</p>
      </div>
      <a class="btn btn--dourado" href="{e(url)}" target="_blank" rel="noopener">Seguir no Instagram</a>
    </div>
  </div>
</section>"""


# =============================================================== conteúdo ==

def carregar_manutencao() -> dict:
    """
    Le manutencao.local.json (fora do versionamento). Quando ativo, o site
    inteiro fica atras de autenticacao HTTP do Apache — o servidor nao entrega
    nem o HTML sem a senha, diferente de uma tela de senha em JavaScript, que
    manda a pagina toda para o navegador e so esconde visualmente.
    """
    arq = RAIZ / "manutencao.local.json"
    if not arq.exists():
        return {"ativa": False}

    dados = limpar_meta(ler_json(arq))
    if not dados.get("ativa"):
        return {"ativa": False}

    if not preenchido(dados.get("hash")):
        bloqueio("manutencao.local.json tem ativa=true mas nao tem hash de senha. "
                 "Se for teste local, desative ativa=true; se for publicar, rode: "
                 ".\\manutencao.ps1 -Ativar")
        return {"ativa": False}

    if not preenchido(dados.get("caminho_no_servidor")):
        bloqueio("manutencao.local.json tem ativa=true mas 'caminho_no_servidor' esta "
                 "vazio. O Apache exige o caminho ABSOLUTO do .htpasswd no servidor; "
                 "se for teste local, desative ativa=true; se for publicar, preencha "
                 "esse campo. Pegue em hPanel > Arquivos > Gerenciador de Arquivos, ou "
                 "rode .\\manutencao.ps1 -Descobrir")
        return {"ativa": False}

    return dados


def carregar_curadoria_midia() -> dict:
    """Le conteudo/curadoria_midia.json — a seleção manual (feita por um humano,
    olhando cada foto) de quais imagens de cada fazenda são boas o suficiente
    para aparecer publicamente e em que ordem.

    Formato esperado por fazenda (chave = slug = nome do arquivo .json sem
    extensão): {"fotos_curadas": ["foto-02.jpg", ...], "excluidas": [...]}.
    "excluidas" é só documentação (motivo do descarte) e não é usada no build.

    Fazendas ausentes deste arquivo (ex.: os imóveis de exemplo/modelo) usam o
    comportamento antigo — todas as fotos da pasta, na ordem do campo "fotos"
    do JSON do imóvel.
    """
    caminho = CONTEUDO / "curadoria_midia.json"
    if not caminho.exists():
        return {}
    bruto = ler_json(caminho)
    if not isinstance(bruto, dict):
        return {}
    return bruto


def carregar_imoveis() -> list[dict]:
    itens = []
    pasta = CONTEUDO / "imoveis"
    if not pasta.exists():
        return itens

    curadoria = carregar_curadoria_midia()

    for arq in sorted(pasta.glob("*.json")):
        if arq.name.startswith("_"):
            continue
        dados = ler_json(arq)
        if not dados:
            continue
        d = limpar_meta(dados)
        d["slug"] = arq.stem
        d["url"] = f"/imoveis/{arq.stem}/"
        d["arquivo"] = arq.name

        if not d.get("titulo"):
            aviso(f"{arq.name}: sem título — imóvel ignorado.")
            continue

        if not d.get("publicado"):
            if not MOSTRAR_RASCUNHOS:
                continue
            d["_rascunho"] = True

        if "EXEMPLO" in str(d.get("titulo", "")).upper():
            d["_exemplo"] = True

        area = d.get("area_total_ha") or 0
        preco = d.get("preco") or 0
        d["preco_ha"] = (preco / area) if (area and preco and not d.get("preco_sob_consulta")) else 0

        pasta_fotos = d.get("pasta_fotos") or arq.stem

        # A galeria pública e a capa vêm EXCLUSIVAMENTE da curadoria manual
        # (conteudo/curadoria_midia.json) quando ela existir para esta fazenda.
        # Isso é proposital: o banco de mídia bruto mistura fotos boas com
        # prints de slide, print de mapa/app, foto de dentro do carro etc., e
        # não queremos que isso volte a vazar para o site s
        # ó porque alguém adicionou um arquivo novo na pasta sem repassar a
        # curadoria. Fazendas sem entrada na curadoria (ex.: imóveis de
        # exemplo) caem no comportamento antigo: todas as fotos do campo
        # "fotos" do JSON, na ordem em que foram listadas.
        entrada_curadoria = curadoria.get(arq.stem)
        if entrada_curadoria is not None:
            # Existe entrada na curadoria para esta fazenda — vale mesmo que
            # a lista esteja vazia (fazenda sem nenhuma foto aproveitável
            # após a exclusão de prints/mapas/etc.). Não caímos de volta para
            # "fotos" nesse caso: mostrar a pasta bruta sem curadoria é
            # exatamente o que essa curadoria existe para evitar.
            fotos = entrada_curadoria.get("fotos_curadas") or []
            d["_fotos_curadas"] = True
            if not fotos:
                aviso(f"{arq.name}: curadoria de mídia não deixou nenhuma foto utilizável "
                      f"para esta fazenda — precisa de nova sessão fotográfica.")
        else:
            fotos = d.get("fotos") or []
            d["_fotos_curadas"] = False

        d["fotos_url"] = [f"/midia/imoveis/{pasta_fotos}/{f}" for f in fotos]
        for f in fotos:
            origem = CONTEUDO / "midia" / "imoveis" / pasta_fotos / f
            if not origem.exists():
                aviso(f"{arq.name}: a foto '{f}' não existe em conteudo/midia/imoveis/{pasta_fotos}/ "
                      f"(vinda de {'curadoria_midia.json' if entrada_curadoria else 'fotos'}).")

        itens.append(d)

    itens.sort(key=lambda x: (not x.get("destaque"), x.get("titulo", "")))
    return itens


def carregar_posts() -> list[dict]:
    posts = []
    pasta = CONTEUDO / "noticias"
    if not pasta.exists():
        return posts

    for arq in sorted(pasta.glob("*.md")):
        if arq.name.startswith("_"):
            continue
        meta, corpo = ler_markdown_com_frontmatter(arq)
        rascunho = not meta.get("publicado")
        if rascunho and not MOSTRAR_RASCUNHOS:
            continue
        if not meta.get("titulo"):
            aviso(f"{arq.name}: sem 'titulo' no cabeçalho — post ignorado.")
            continue

        try:
            d = datetime.strptime(str(meta.get("data", "")).strip(), "%Y-%m-%d").date()
        except ValueError:
            aviso(f"{arq.name}: data ausente ou fora do formato AAAA-MM-DD. Usando hoje.")
            d = date.today()

        n_palavras = len(re.findall(r"\S+", corpo))
        tempo_leitura = max(1, round(n_palavras / 200))

        posts.append({
            "titulo": meta["titulo"],
            "resumo": meta.get("resumo", ""),
            "autor": meta.get("autor", "Prime Fazendas"),
            "categoria": meta.get("categoria", "Insights"),
            "capa": meta.get("capa", ""),
            "data": d,
            "slug": arq.stem,
            "url": f"/blog/{arq.stem}/",
            "html": markdown(corpo),
            "tempo_leitura": tempo_leitura,
            "arquivo": arq.name,
            "_rascunho": rascunho,
        })

    posts.sort(key=lambda p: p["data"], reverse=True)
    return posts


def carregar_agenda_agro() -> list[dict]:
    """Le conteudo/agenda-agro.json e devolve so os eventos publicados, com
    datas futuras ou em curso, ordenados por data de inicio."""
    caminho = CONTEUDO / "agenda-agro.json"
    if not caminho.exists():
        return []
    bruto = limpar_meta(ler_json(caminho))
    eventos = []
    hoje = date.today()
    for ev in bruto.get("eventos", []):
        if not ev.get("publicado"):
            continue
        nome = str(ev.get("nome", "")).strip()
        if not nome:
            aviso("agenda-agro.json: evento sem 'nome' foi ignorado.")
            continue
        try:
            d_ini = datetime.strptime(str(ev.get("data_inicio", "")).strip(), "%Y-%m-%d").date()
        except ValueError:
            aviso(f"agenda-agro.json: '{nome}' com data_inicio ausente ou fora do formato AAAA-MM-DD — evento ignorado.")
            continue
        d_fim = None
        if str(ev.get("data_fim", "")).strip():
            try:
                d_fim = datetime.strptime(str(ev["data_fim"]).strip(), "%Y-%m-%d").date()
            except ValueError:
                aviso(f"agenda-agro.json: '{nome}' com data_fim fora do formato AAAA-MM-DD — ignorada, mantendo so data_inicio.")

        fim_para_filtro = d_fim or d_ini
        if fim_para_filtro < hoje:
            continue

        eventos.append({
            "nome": nome,
            "cidade": ev.get("cidade", ""),
            "estado": ev.get("estado", ""),
            "data_inicio": d_ini,
            "data_fim": d_fim,
            "url_oficial": ev.get("url_oficial", ""),
            "descricao": ev.get("descricao", ""),
        })

    eventos.sort(key=lambda ev: ev["data_inicio"])
    return eventos


# ================================================================ páginas ==

def card_imovel(im: dict, cambio: dict | None = None) -> str:
    selos = []
    rotulo, classe = STATUS.get(im.get("status", "disponivel"), STATUS["disponivel"])
    if im.get("status") != "disponivel":
        selos.append(f'<span class="selo {classe}">{e(rotulo)}</span>')
    if im.get("certificacao_ambiental"):
        selos.append('<span class="selo">Documentação verificada</span>')
    if im.get("_rascunho"):
        selos.append('<span class="selo selo--aviso">Rascunho — não publicado</span>')
    if im.get("_exemplo"):
        selos.append('<span class="selo selo--aviso">Exemplo</span>')

    local = ", ".join(x for x in [im.get("municipio"), im.get("estado")] if x)
    alt_capa = descricao_foto(im["fotos_url"][0], im["titulo"], local) if im["fotos_url"] else (
        f'{im["titulo"]} — {local}' if local else im["titulo"])

    if im["fotos_url"]:
        # A capa do card é sempre a primeira foto do conjunto CURADO (ver
        # carregar_imoveis / curadoria_midia.json) — a melhor foto escolhida
        # manualmente para representar a fazenda em uma única imagem.
        largura_capa, altura_capa = dimensoes_midia_url(im["fotos_url"][0], 1200, 750)
        capa = (f'<a class="imovel__capa-link js-foto-modal" href="{e(im["fotos_url"][0])}" '
                f'data-foto-modal-src="{e(im["fotos_url"][0])}" '
                f'data-foto-modal-alt="{e(alt_capa)}" '
                f'title="Abrir foto no visualizador">'
                f'<img src="{e(im["fotos_url"][0])}" alt="{e(alt_capa)}" '
                f'width="{largura_capa}" height="{altura_capa}" loading="lazy" sizes="(max-width: 640px) 100vw, 50vw">'
                f'</a>')
    else:
        capa = SVG_CAPA

    tipo = TIPOS.get(im.get("tipo", ""), "")
    cabeca = " · ".join(x for x in [local, tipo] if x)

    dados = []
    if im.get("area_total_ha"):
        dados.append(f'<div class="dado"><span class="dado__rot">Área total</span>'
                     f'<span class="dado__val">{fmt_num(im["area_total_ha"])} ha</span></div>')
    if im.get("preco_sob_consulta") or not im.get("preco"):
        dados.append('<div class="dado"><span class="dado__rot">Valor</span>'
                     '<span class="dado__val dado__val--preco">Sob consulta</span></div>')
    else:
        dados.append(f'<div class="dado"><span class="dado__rot">Valor</span>'
                     f'<span class="dado__val dado__val--preco">{e(fmt_reais(im["preco"]))}'
                     f'{preco_usd_html(im["preco"], cambio)}</span></div>')
    preco_ordenacao = im["preco"] if im.get("preco") and not im.get("preco_sob_consulta") else 0
    area_ordenacao = im.get("area_total_ha") or 0

    return f"""<article class="imovel reveal" data-tipo="{e(im.get('tipo', ''))}" data-preco="{preco_ordenacao}" data-area="{area_ordenacao}">
  <div class="imovel__capa">
    {f'<div class="imovel__selos">{"".join(selos)}</div>' if selos else ''}
    {capa}
  </div>
  <div class="imovel__corpo">
    <p class="imovel__local">{e(cabeca)}</p>
    <h3 class="imovel__titulo"><a href="{e(im['url'])}">{e(im['titulo'])}</a></h3>
    <div class="imovel__dados">{''.join(dados)}</div>
  </div>
</article>"""


def gerar_home(cfg, pag, imoveis, posts, dados_agro, depoimentos) -> str:
    h = pag.get("home", {})
    zap = montar_url_zap(cfg)

    botoes = f'<a class="btn btn--dourado" href="/imoveis/">{e(h.get("hero_cta", "Ver imóveis"))}</a>'
    if zap:
        botoes += (f'<a class="btn btn--claro" href="{e(zap)}" target="_blank" rel="noopener">'
                   f'{e(h.get("hero_cta_secundario", "Falar com um especialista"))}</a>')
    else:
        botoes += (f'<a class="btn btn--claro" href="/contato/">'
                   f'{e(h.get("hero_cta_secundario", "Falar com um especialista"))}</a>')

    corpo = [hero(cfg, olho=f"{cfg['contato'].get('cidade', '')} · {cfg['contato'].get('estado', '')} · Matopiba".strip(" ·"),
                  titulo=h.get("hero_titulo", cfg["marca"]["slogan"]),
                  texto=h.get("hero_texto", ""), botoes=botoes, foto="/midia/imoveis/fazenda-amazonita/aerea-02.jpg")]

    # pilares
    cards = "".join(
        f'<article class="card reveal">'
        f'<div class="card__icone">{ICONES_PILARES[i % len(ICONES_PILARES)]}</div>'
        f'<div class="card__num">{numeral_romano(i + 1)}</div>'
        f'<h3>{e(p["titulo"])}</h3><p>{e(p["texto"])}</p></article>'
        for i, p in enumerate(h.get("pilares", []))
    )
    if cards:
        corpo.append(f"""<section class="secao secao--clara">
  <div class="env">
    <div class="cabeca-secao">
      <p class="olho">Por que a Prime</p>
      <h2>{e(h.get('faixa_titulo', ''))}</h2>
      <p class="chamada chamada--larga">{e(h.get('faixa_texto', ''))}</p>
    </div>
    <div class="grade grade--4">{cards}</div>
  </div>
</section>""")

    # destaques
    destaques = [i for i in imoveis if i.get("destaque")] or imoveis[:3]
    if destaques:
        corpo.append(f"""<section class="secao secao--clara">
  <div class="env">
    <div class="cabeca-secao">
      <p class="olho">Oportunidades</p>
      <h2>Propriedades em destaque</h2>
      <p class="chamada chamada--larga">Portfólio verificado. Cada propriedade passou por análise
      documental, ambiental e de mercado antes de ser apresentada.</p>
    </div>
    <div class="grade-imoveis">{''.join(card_imovel(i, cambio=cfg.get('cambio')) for i in destaques[:3])}</div>
    <p style="margin-top:2.5rem"><a class="link-seta" href="/imoveis/">Ver todas as propriedades</a></p>
  </div>
</section>""")

    # indicadores verificados
    indics = [i for i in dados_agro.get("indicadores", []) if not i.get("verificar")]
    if indics:
        blocos = ""
        for i in indics:
            fonte = f'{e(i.get("fonte", ""))} · {e(i.get("ano", ""))}'
            if preenchido(i.get("url")):
                fonte = f'<a href="{e(i["url"])}" target="_blank" rel="noopener">{fonte}</a>'
            blocos += (f'<div class="indic"><span class="indic__valor">{e(i.get("valor", ""))}</span>'
                       f'<p class="indic__rotulo">{e(i.get("rotulo", ""))}</p>'
                       f'<p class="indic__fonte">{fonte}</p></div>')
        corpo.append(f"""<section class="secao secao--escura">
  <div class="env">
    <div class="grade grade--3">{blocos}</div>
  </div>
</section>""")

    # depoimentos publicados
    pubs = [d for d in depoimentos.get("depoimentos", []) if d.get("publicado")]
    if pubs:
        cards_dep = "".join(
            f'<article class="card"><p style="font-family:var(--fonte-display);font-size:1.1rem;'
            f'color:var(--azul-800);margin-bottom:1.2rem">“{e(d["texto"])}”</p>'
            f'<p><strong>{e(d["nome"])}</strong>'
            + (f'<br><span style="font-size:.88rem;color:var(--tinta-suave)">{e(d.get("cargo", ""))}</span>'
               if d.get("cargo") else "")
            + "</p></article>"
            for d in pubs[:3]
        )
        corpo.append(f"""<section class="secao secao--branca">
  <div class="env">
    <div class="cabeca-secao cabeca-secao--centro">
      <p class="olho olho--centro">Quem já negociou com a gente</p>
      <h2>Depoimentos</h2>
    </div>
    <div class="grade grade--3">{cards_dep}</div>
  </div>
</section>""")

    # últimos posts
    if posts:
        cards_post = "".join(card_post(p) for p in posts[:3])
        corpo.append(f"""<section class="secao secao--clara">
  <div class="env">
    <div class="cabeca-secao">
      <p class="olho">Insights</p>
      <h2>Do mercado de terras</h2>
    </div>
    <div class="grade-posts">{cards_post}</div>
  </div>
</section>""")

    ig = bloco_instagram(cfg)
    if ig:
        corpo.append(ig)

    corpo.append(cta_faixa(
        cfg,
        "Vamos conversar sobre a sua próxima propriedade.",
        "Comprar, vender, avaliar ou regularizar. Conte o que você precisa e um especialista responde.",
    ))

    ld = json.dumps({
        "@context": "https://schema.org",
        "@type": "RealEstateAgent",
        "name": cfg["marca"]["nome"],
        "description": cfg["site"]["descricao_padrao"],
        "url": cfg["site"]["dominio"],
        "slogan": cfg["marca"]["slogan"],
        "areaServed": {"@type": "State", "name": "Tocantins"},
        **({"telephone": cfg["contato"]["telefone"]} if preenchido(cfg["contato"].get("telefone")) else {}),
        **({"email": cfg["contato"]["email"]} if preenchido(cfg["contato"].get("email")) else {}),
        "address": {
            "@type": "PostalAddress",
            "addressLocality": cfg["contato"].get("cidade", ""),
            "addressRegion": cfg["contato"].get("estado", ""),
            "addressCountry": cfg["contato"].get("pais", "BR"),
        },
    }, ensure_ascii=False)

    ld_migalha = ld_breadcrumbs(cfg, [("Início", "/")])

    return pagina(cfg, titulo=cfg["site"]["titulo_padrao"],
                  descricao=cfg["site"].get("descricao_meta", cfg["site"]["descricao_padrao"]), url="/",
                  corpo="\n".join(corpo), json_ld=[ld, ld_migalha],
                  rascunho=any(i.get("_exemplo") or i.get("_rascunho") for i in imoveis),
                  hreflang=hreflang_para(cfg, "/"))


ICONE_NOTICIA_FOLHA = ('<svg viewBox="0 0 24 24" aria-hidden="true">'
                       '<path d="M5 19c7-1 12-6 13-13-7 1-12 6-13 13Z"/>'
                       '<path d="M6.5 17.5c2-4 5-7 9-9"/></svg>')
ICONE_NOTICIA_GOTA = ('<svg viewBox="0 0 24 24" aria-hidden="true">'
                      '<path d="M12 3.5s6 7 6 11a6 6 0 0 1-12 0c0-4 6-11 6-11Z"/></svg>')
ICONE_NOTICIA_EXPORT = ('<svg viewBox="0 0 24 24" aria-hidden="true">'
                        '<path d="M7 17 17 7M9.5 7H17v7.5"/></svg>')
ICONE_NOTICIA_MOEDA = ('<svg viewBox="0 0 24 24" aria-hidden="true">'
                       '<circle cx="12" cy="12" r="8"/>'
                       '<path d="M12 7.2v9.6M9.3 9.6c0-1.4 1.2-2.4 2.7-2.4s2.6.9 2.6 2.1c0 2.7-5.3 1.6-5.3 4.2 0 1.3 1.2 2.3 2.7 2.3s2.7-1 2.7-2.3"/></svg>')


def icone_noticia(categoria: str) -> str:
    c = (categoria or "").lower()
    if "clima" in c or "chuva" in c or "hídric" in c or "hidric" in c or "água" in c or "agua" in c:
        return ICONE_NOTICIA_GOTA
    if "exporta" in c or "logíst" in c or "logist" in c:
        return ICONE_NOTICIA_EXPORT
    if "financ" in c or "crédit" in c or "credit" in c or "investi" in c:
        return ICONE_NOTICIA_MOEDA
    return ICONE_NOTICIA_FOLHA


def card_post(p: dict, destaque: bool = False) -> str:
    tempo = p.get('tempo_leitura')
    meta_tempo = f'<span>·</span><span>{tempo} min de leitura</span>' if tempo else ''
    classe = "post-card post-card--destaque reveal" if destaque else "post-card reveal"
    if preenchido(p.get('capa')):
        largura_post, altura_post = dimensoes_midia_url(p["capa"], 640, 400)
        capa = (f'<a class="post-card__capa post-card__capa--foto" href="{e(p["url"])}" '
                f'aria-hidden="true" tabindex="-1">'
                f'<img src="{e(p["capa"])}" alt="{e(p["titulo"])}" loading="lazy" '
                f'width="{largura_post}" height="{altura_post}">'
                f'<span class="post-card__selo">Prime News</span>'
                f'<span class="post-card__icone">{icone_noticia(p["categoria"])}</span>'
                f'</a>')
    else:
        capa = (f'<a class="post-card__capa" href="{e(p["url"])}" aria-hidden="true" tabindex="-1">'
                f'<span class="post-card__selo">Prime News</span>'
                f'<span class="post-card__icone">{icone_noticia(p["categoria"])}</span>'
                f'</a>')
    return f"""<article class="{classe}">
  {capa}
  <div class="post-card__corpo">
    <p class="post-card__meta"><span class="post-card__cat">{e(p['categoria'])}</span>
    <span>·</span><time datetime="{p['data'].isoformat()}">{e(fmt_data(p['data']))}</time>
    {meta_tempo}</p>
    <h3><a href="{e(p['url'])}">{e(p['titulo'])}</a></h3>
    {f"<p>{e(p['resumo'])}</p>" if p.get('resumo') else ''}
    <a class="link-seta" href="{e(p['url'])}">Ler o artigo</a>
  </div>
</article>"""


def gerar_sobre(cfg, pag) -> str:
    s = pag.get("sobre", {})
    c = cfg["contato"]
    corpo = [hero(cfg, olho="Sobre nós", titulo=s.get("titulo", "Sobre a Prime Fazendas"),
                  texto=s.get("chamada", ""), interno=True, foto="/midia/imoveis/fazenda-diamante/foto-02.jpg")]
    corpo.append(f"""<section class="secao">
  <div class="env">
    <div class="prosa">
      <p class="olho">Quem somos</p>
      {paragrafos(s.get('quem_somos'))}
    </div>
  </div>
</section>""")

    # credenciais verificaveis — apenas dados reais ja cadastrados, sem numero inventado
    credenciais = []
    if preenchido(c.get("creci")):
        credenciais.append(("CRECI", e(c["creci"])))
    cidade_uf = ", ".join(x for x in [c.get("cidade"), c.get("estado")] if preenchido(x))
    if cidade_uf:
        credenciais.append(("Sede", e(cidade_uf)))
    if preenchido(cfg["marca"].get("ano_fundacao")):
        credenciais.append(("Fundada em", e(cfg["marca"]["ano_fundacao"])))
    ig = cfg.get("redes", {}).get("instagram")
    if preenchido(ig):
        icone_ig = ICONES_REDE.get("instagram", "")
        credenciais.append(("Instagram", f'<a class="link-icone" href="{e(ig)}" target="_blank" rel="noopener">'
                           f'<span class="link-icone__svg" aria-hidden="true">{icone_ig}</span>'
                           f'perfil verificado</a>'))
    if credenciais:
        creds_html = "".join(
            f'<div class="dado"><span class="dado__rot">{r}</span><span class="dado__val">{v}</span></div>'
            for r, v in credenciais
        )
        corpo.append(f"""<section class="secao secao--compacta">
  <div class="env">
    <div class="imovel__dados imovel__dados--ficha">{creds_html}</div>
  </div>
</section>""")

    corpo.append(f"""<section class="secao secao--clara">
  <div class="env">
    <div class="prosa">
      <p class="olho">Investidores fora do Brasil</p>
      <h2>Atendemos parceiros internacionais</h2>
      <p>Parte da nossa rede de compradores e investidores está no exterior, incluindo parceiros comerciais
      na Europa. Orientamos o processo de aquisição para quem vive fora do Brasil — documentação necessária,
      etapas de due diligence e o passo a passo até a assinatura — sempre em conjunto com advogados e
      despachantes habilitados, já que a Prime Fazendas atua na intermediação imobiliária e não presta
      assessoria jurídica. Fale com a gente em português ou, se preferir, coordenamos o atendimento em
      inglês mediante combinação prévia.</p>
    </div>
  </div>
</section>""")

    corpo.append(f"""<section class="secao secao--clara">
  <div class="env">
    <div class="prosa">
      <p class="olho">{e(s.get('historia_titulo', 'A história'))}</p>
      <h2>De corretor aos 18 ao coração do agro brasileiro</h2>
      {paragrafos(s.get('historia'))}
    </div>
  </div>
</section>""")

    _sobre_foto = "/midia/imoveis/fazenda-citrino/aerea-03.jpg"
    _sobre_foto_w, _sobre_foto_h = dimensoes_midia_url(_sobre_foto, 1600, 1000)
    corpo.append(f"""<section class="secao secao--compacta">
  <div class="env">
    <figure class="sobre-foto">
      <img src="{_sobre_foto}" alt="Pastagem formada em uma das propriedades do portfólio Prime Fazendas" width="{_sobre_foto_w}" height="{_sobre_foto_h}" loading="lazy">
      <figcaption>Imagem ilustrativa do acervo Prime Fazendas — chão de fazenda, todos os dias.</figcaption>
    </figure>
  </div>
</section>""")

    difs = "".join(
        f'<article class="card"><h3>{e(d["titulo"])}</h3><p>{e(d["texto"])}</p></article>'
        for d in s.get("diferenciais", [])
    )
    corpo.append(f"""<section class="secao">
  <div class="env">
    <div class="cabeca-secao">
      <p class="olho">{e(s.get('diferenciais_titulo', 'Nosso diferencial'))}</p>
      <h2>O que fazemos diferente</h2>
      <p class="chamada chamada--larga">{e(s.get('diferenciais_texto', ''))}</p>
    </div>
    <div class="grade grade--2">{difs}</div>
  </div>
</section>""")

    parceiros_lista = s.get("parceiros", [])
    if parceiros_lista:
        parceiros_cards = "".join(
            f'<article class="card"><h3>{e(pnr["nome"])}</h3><p>{e(pnr["texto"])}</p></article>'
            for pnr in parceiros_lista
        )
        corpo.append(f"""<section class="secao secao--clara">
  <div class="env">
    <div class="cabeca-secao">
      <p class="olho">Parceiros</p>
      <h2>{e(s.get('parceiros_titulo', 'Parceiros estratégicos'))}</h2>
      <p class="chamada chamada--larga">{e(s.get('parceiros_intro', ''))}</p>
    </div>
    <div class="grade grade--2">{parceiros_cards}</div>
  </div>
</section>""")

    valores = "".join(f"<li>{e(v)}</li>" for v in s.get("valores", []))
    corpo.append(f"""<section class="secao secao--escura">
  <div class="env">
    <div class="grade grade--2" style="align-items:start">
      <div>
        <p class="olho">{e(s.get('missao_titulo', 'Nossa missão'))}</p>
        <h2>Missão</h2>
        <p class="chamada">{e(s.get('missao', ''))}</p>
      </div>
      <div>
        <p class="olho">Valores</p>
        <ul class="marcada marcada--check">{valores}</ul>
      </div>
    </div>
  </div>
</section>""")

    corpo.append(cta_faixa(cfg, "Quer conhecer o nosso portfólio?",
                           "Boa parte das nossas negociações acontece antes do anúncio público."))

    redes_sameas = [u for u in cfg.get("redes", {}).values() if preenchido(u)]
    ld = json.dumps({
        "@context": "https://schema.org",
        "@type": "AboutPage",
        "name": s.get("titulo", "Sobre nós"),
        "mainEntity": {
            "@type": "Organization",
            "name": cfg["marca"]["nome"],
            "url": cfg["site"]["dominio"],
            "description": cfg["marca"].get("descricao_curta", cfg["site"]["descricao_padrao"]),
            **({"foundingDate": str(cfg["marca"]["ano_fundacao"])} if preenchido(cfg["marca"].get("ano_fundacao")) else {}),
            "address": {
                "@type": "PostalAddress",
                "addressLocality": c.get("cidade", ""),
                "addressRegion": c.get("estado", ""),
                "addressCountry": c.get("pais", "BR"),
            },
            **({"sameAs": redes_sameas} if redes_sameas else {}),
        },
    }, ensure_ascii=False)
    ld_migalha = ld_breadcrumbs(cfg, [("Início", "/"), ("Sobre Nós", "/sobre/")])

    return pagina(cfg, titulo=s.get("titulo", "Sobre nós"),
                  descricao=s.get("descricao_meta", s.get("chamada", cfg["site"]["descricao_padrao"])),
                  url="/sobre/", corpo="\n".join(corpo), json_ld=[ld, ld_migalha],
                  hreflang=hreflang_para(cfg, "/sobre/"))


def gerar_servicos(cfg, pag) -> str:
    s = pag.get("servicos", {})
    corpo = [hero(cfg, olho="Serviços", titulo=s.get("titulo", "Nossos serviços"),
                  texto=s.get("chamada", ""), interno=True, foto="/midia/imoveis/fazenda-citrino/aerea-03.jpg")]

    cards = "".join(
        f'<article class="card"><div class="card__num">{numeral_romano(i + 1)}</div>'
        f'<h3>{e(x["titulo"])}</h3><p>{e(x["texto"])}</p></article>'
        for i, x in enumerate(s.get("lista", []))
    )
    corpo.append(f"""<section class="secao">
  <div class="env"><div class="grade grade--2">{cards}</div></div>
</section>""")

    corpo.append(cta_faixa(cfg, s.get("cta_titulo", "Cada propriedade é um caso."),
                           s.get("cta_texto", ""), s.get("cta_botao", "Solicitar consultoria")))

    ld = json.dumps({
        "@context": "https://schema.org",
        "@type": "Service",
        "name": s.get("titulo", "Serviços"),
        "description": s.get("chamada", ""),
        "provider": {"@type": "RealEstateAgent", "name": cfg["marca"]["nome"], "url": cfg["site"]["dominio"]},
        "areaServed": {"@type": "State", "name": "Tocantins"},
        **({"hasOfferCatalog": {
            "@type": "OfferCatalog",
            "name": "Serviços Prime Fazendas",
            "itemListElement": [
                {"@type": "Offer", "itemOffered": {"@type": "Service", "name": x["titulo"], "description": x.get("texto", "")}}
                for x in s.get("lista", [])
            ],
        }} if s.get("lista") else {}),
    }, ensure_ascii=False)
    ld_migalha = ld_breadcrumbs(cfg, [("Início", "/"), ("Serviços", "/servicos/")])

    return pagina(cfg, titulo=s.get("titulo", "Serviços"),
                  descricao=s.get("descricao_meta", s.get("chamada", "")), url="/servicos/",
                  corpo="\n".join(corpo), json_ld=[ld, ld_migalha],
                  hreflang=hreflang_para(cfg, "/servicos/"))


def gerar_datacenter(cfg, pag) -> str:
    s = pag.get("datacenter", {})
    zap = montar_url_zap(cfg)

    botoes_hero = f'<a class="btn btn--dourado" href="#modelos">Ver modelos e medidas</a>'
    if zap:
        botoes_hero += f'<a class="btn btn--claro" href="{e(zap)}" target="_blank" rel="noopener">Falar no WhatsApp agora</a>'

    corpo = [hero(cfg, olho=s.get("olho", "Nova frente Prime Fazendas"),
                  titulo=s.get("chamada", "Estruturas de Data Center"),
                  texto=s.get("hero_texto", ""), botoes=botoes_hero, interno=True,
                  foto=s.get("foto_hero", ""))]

    pilares = "".join(
        f'<article class="card"><div class="card__num">{e(p.get("num",""))}</div>'
        f'<h3>{e(p.get("titulo",""))}</h3><p>{e(p.get("texto",""))}</p></article>'
        for p in s.get("pilares", [])
    )
    if pilares:
        corpo.append(f"""<section class="secao secao--branca">
  <div class="env">
    <div class="cabeca-secao cabeca-secao--centro">
      <p class="olho olho--centro">Nosso negócio, em uma frase</p>
      <h2>Compra, venda e estruturação de Data Center — do terreno à obra entregue</h2>
      <p class="chamada chamada--larga" style="margin-inline:auto">A Prime Fazendas atua nas três pontas do projeto: vende o ativo certo, estrutura o negócio para ele sair do papel e administra a construção até a entrega.</p>
    </div>
    <div class="grade grade--3">{pilares}</div>
  </div>
</section>""")

    galeria = s.get("galeria", [])
    if galeria:
        itens_galeria = "".join(
            f'<a class="galeria__link js-foto-modal" href="{e(g["foto"])}" '
            f'data-foto-modal-src="{e(g["foto"])}" '
            f'data-foto-modal-alt="{e(g.get("legenda",""))}" '
            f'title="Abrir foto no visualizador">'
            f'<img src="{e(g["foto"])}" alt="{e(g.get("legenda",""))}" '
            f'width="{(dim := dimensoes_midia_url(g["foto"], 1200, 800))[0]}" height="{dim[1]}" '
            f'loading="lazy" sizes="(max-width: 640px) 100vw, 50vw">'
            f'</a>'
            for g in galeria
        )
        corpo.append(f"""<section class="secao secao--clara">
  <div class="env">
    <div class="cabeca-secao cabeca-secao--centro">
      <p class="olho olho--centro">Referências reais</p>
      <h2>O tipo de estrutura que vendemos e viabilizamos</h2>
      <p class="chamada chamada--larga" style="margin-inline:auto">Prédios de grande porte, salas cheias de máquinas em operação e a infraestrutura elétrica que sustenta tudo isso.</p>
    </div>
    <div class="galeria galeria--curada galeria--datacenter">{itens_galeria}</div>
  </div>
</section>""")

    modelos = s.get("modelos", [])
    if modelos:
        cards = "".join(
            f'<article class="card"><div class="card__num">{e(m.get("potencia",""))}</div>'
            f'<h3>{e(m.get("nome",""))}</h3><p>{e(m.get("desc",""))}</p>'
            f'<p class="link-seta" style="margin-top:1rem"><a class="link-seta" href="#modelo-{e(m.get("id",""))}">Ver especificações</a></p></article>'
            for m in modelos
        )
        detalhes = ""
        for m in modelos:
            btn_modelo = ""
            if zap:
                btn_modelo = f'<a class="btn btn--dourado btn--bloco" href="{e(zap)}" target="_blank" rel="noopener">Falar sobre o modelo {e(m.get("nome",""))}</a>'
            detalhes += f"""<div class="painel" id="modelo-{e(m.get('id',''))}" style="position:static; margin-bottom:1.5rem; scroll-margin-top:100px;">
      <h3 style="margin-bottom:.3rem">{e(m.get('nome',''))}</h3>
      <p class="painel__preco-nota">{e(m.get('potencia',''))}</p>
      <ul class="painel__linhas">
        <li><span class="rot">Área estimada do terreno</span><span class="val">{e(m.get('area',''))}</span></li>
        <li><span class="rot">Capacidade estimada de racks</span><span class="val">{e(m.get('racks',''))}</span></li>
        <li><span class="rot">Redundância</span><span class="val">{e(m.get('redundancia',''))}</span></li>
        <li><span class="rot">Prazo estimado de entrega</span><span class="val">{e(m.get('prazo',''))}</span></li>
        <li><span class="rot">Público ideal</span><span class="val" style="text-align:right; max-width:60%">{e(m.get('publico',''))}</span></li>
      </ul>
      {btn_modelo}
    </div>"""

        corpo.append(f"""<section class="secao secao--branca" id="modelos">
  <div class="env">
    <div class="cabeca-secao cabeca-secao--centro">
      <p class="olho olho--centro">Modelos e medidas</p>
      <h2>Três cenários de referência — ou projeto sob medida</h2>
    </div>
    <div class="grade grade--3">{cards}</div>
    <div style="margin-top:2.5rem">{detalhes}</div>
    <p class="nota-modelos" style="font-size:.85rem;color:var(--tinta-suave);margin-top:1.5rem;max-width:70ch">{e(s.get("nota_modelos",""))}</p>
  </div>
</section>""")

    faq = s.get("faq", [])
    if faq:
        faq_html = "".join(
            f'<details class="ficha-tecnica" style="margin-top:0"><summary class="ficha-tecnica__abrir">{e(qa.get("pergunta",""))}</summary>'
            f'<div class="ficha-tecnica__corpo"><p>{e(qa.get("resposta",""))}</p></div></details>'
            for qa in faq
        )
        corpo.append(f"""<section class="secao">
  <div class="env">
    <div class="cabeca-secao cabeca-secao--centro">
      <p class="olho olho--centro">Perguntas frequentes</p>
      <h2>Dúvidas comuns sobre venda e estruturação de Data Center</h2>
    </div>
    {faq_html}
  </div>
</section>""")

    corpo.append(cta_faixa(cfg, s.get("cta_titulo", "Pronto para tirar o seu Data Center do papel?"),
                           s.get("cta_texto", ""), s.get("cta_botao", "Falar sobre meu projeto de Data Center")))

    modelos_schema = [
        {
            "@type": "Product",
            "name": m.get("nome", ""),
            "description": m.get("desc", ""),
            "additionalProperty": [
                {"@type": "PropertyValue", "name": "Potência", "value": m.get("potencia", "")},
                {"@type": "PropertyValue", "name": "Área estimada", "value": m.get("area", "")},
                {"@type": "PropertyValue", "name": "Redundância", "value": m.get("redundancia", "")},
            ],
        }
        for m in modelos
    ]

    ld_service = json.dumps({
        "@context": "https://schema.org",
        "@type": "Service",
        "name": s.get("titulo", "Estruturas de Data Center"),
        "description": s.get("descricao_meta", s.get("chamada", "")),
        "provider": {"@type": "RealEstateAgent", "name": cfg["marca"]["nome"], "url": cfg["site"]["dominio"]},
        "areaServed": [{"@type": "Country", "name": "Brasil"}, {"@type": "Place", "name": "Mundo"}],
        **({"image": [{"@type": "ImageObject", "contentUrl": cfg["site"]["dominio"].rstrip("/") + g["foto"],
                       "caption": g.get("legenda", ""),
                       "width": dimensoes_midia_url(g["foto"], 1200, 800)[0],
                       "height": dimensoes_midia_url(g["foto"], 1200, 800)[1]}
                      for g in galeria]} if galeria else {}),
        **({"hasOfferCatalog": {
            "@type": "OfferCatalog",
            "name": "Modelos de Data Center Prime Fazendas",
            "itemListElement": modelos_schema,
        }} if modelos_schema else {}),
    }, ensure_ascii=False)

    ld_faq = ""
    if faq:
        ld_faq = json.dumps({
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": qa.get("pergunta", ""),
                 "acceptedAnswer": {"@type": "Answer", "text": qa.get("resposta", "")}}
                for qa in faq
            ],
        }, ensure_ascii=False)

    ld_migalha = ld_breadcrumbs(cfg, [("Início", "/"), ("Data Center", "/data-center/")])

    dominio = cfg["site"]["dominio"].rstrip("/")
    hreflang = [
        ("pt-BR", f"{dominio}/data-center/"),
        ("en", f"{dominio}/en/data-center/"),
        ("zh-Hans", f"{dominio}/zh/data-center/"),
        ("x-default", f"{dominio}/data-center/"),
    ]

    return pagina(cfg, titulo=s.get("titulo", "Estruturas de Data Center"),
                  descricao=s.get("descricao_meta", s.get("chamada", "")), url="/data-center/",
                  corpo="\n".join(corpo), json_ld=[b for b in [ld_service, ld_faq, ld_migalha] if b],
                  hreflang=hreflang)


NAV_I18N = {
    "en": [
        {"titulo": "Home", "url": "/en/"},
        {"titulo": "About Us", "url": "/en/sobre/"},
        {"titulo": "Services", "url": "/en/servicos/"},
        {"titulo": "Data Center", "url": "/en/data-center/"},
        {"titulo": "Properties", "url": "/en/imoveis/"},
        {"titulo": "Invest in Agribusiness", "url": "/en/investir-no-agro/"},
        {"titulo": "News", "url": "/en/blog/"},
        {"titulo": "Contact", "url": "/en/contato/"},
    ],
    "zh": [
        {"titulo": "首页", "url": "/zh/"},
        {"titulo": "关于我们", "url": "/zh/sobre/"},
        {"titulo": "服务项目", "url": "/zh/servicos/"},
        {"titulo": "数据中心", "url": "/zh/data-center/"},
        {"titulo": "房产项目", "url": "/zh/imoveis/"},
        {"titulo": "投资农业", "url": "/zh/investir-no-agro/"},
        {"titulo": "新闻资讯", "url": "/zh/blog/"},
        {"titulo": "联系我们", "url": "/zh/contato/"},
    ],
}

RODAPE_I18N = {
    "en": {
        "aviso_idioma": "Farm listings and news are now available in English. Some institutional pages remain Portuguese-only for now.",
        "nav_titulo": "Navigation", "contato_titulo": "Contact", "comunidade_titulo": "Community",
        "entrar_comunidade": "Join the community", "noticias": "News and insights", "imoveis": "Properties for sale",
        "direitos": "All rights reserved.",
    },
    "zh": {
        "aviso_idioma": "房产项目及新闻资讯现已提供中文版本。部分公司介绍页面目前仅提供葡萄牙语版本。",
        "nav_titulo": "导航", "contato_titulo": "联系方式", "comunidade_titulo": "社区",
        "entrar_comunidade": "加入社区", "noticias": "新闻与洞察", "imoveis": "在售房产",
        "direitos": "版权所有。",
    },
}


def cabecalho_i18n(cfg: dict, lang: str, url_atual: str) -> str:
    itens = []
    for item in NAV_I18N[lang]:
        atual = ' aria-current="page"' if item["url"] == url_atual else ""
        itens.append(f'<a href="{e(item["url"])}"{atual}>{e(item["titulo"])}</a>')

    zap = montar_url_zap(cfg)
    rotulo_zap = {"en": "Talk on WhatsApp", "zh": "微信/WhatsApp咨询"}[lang]
    cta_mobile = ""
    if zap:
        cta_mobile = f'<a class="btn btn--principal btn--bloco" href="{e(zap)}" target="_blank" rel="noopener">{SVG_ZAP}{rotulo_zap}</a>'
    cta_topo = (
        f'<a class="btn btn--principal" href="{e(zap)}" target="_blank" rel="noopener">{SVG_ZAP}{rotulo_zap}</a>'
        if zap else ""
    )
    subtitulo = {"en": "Rural Real Estate", "zh": "乡村地产"}[lang]

    pt_atual = url_atual.replace(f"/{lang}/", "/", 1) if url_atual != f"/{lang}/" else "/"
    trad = PAGINAS_TRADUZIDAS.get(pt_atual, {})
    outro_lang = "zh" if lang == "en" else "en"
    seletor = seletor_idioma(pt_atual, trad.get("en") or "/en/", trad.get("zh") or "/zh/", lang)

    return f"""<header class="topo">
  <div class="env topo__int">
    <a class="marca" href="/{lang}/" aria-label="{e(cfg['marca']['nome'])}">
      {SVG_SELO}
      <span class="marca__txt">
        <span class="marca__nome">{e(cfg['marca']['nome'])}</span>
        <span class="marca__sub">{e(subtitulo)}</span>
      </span>
    </a>
    <nav class="nav" id="nav-principal" aria-label="Main navigation">
      {''.join(itens)}
      {cta_mobile}
    </nav>
    <div class="topo__acao">
      {seletor}
      {cta_topo}
      <button class="hamburguer" type="button" aria-expanded="false"
              aria-controls="nav-principal" aria-label="Open menu"><span></span></button>
    </div>
  </div>
</header>"""


def rodape_i18n(cfg: dict, lang: str) -> str:
    t = RODAPE_I18N[lang]
    nav = "".join(f'<li><a href="{e(i["url"])}">{e(i["titulo"])}</a></li>' for i in NAV_I18N[lang])

    redes = ""
    for rede, url in cfg.get("redes", {}).items():
        if preenchido(url) and rede in ICONES_REDE:
            redes += (f'<a href="{e(url)}" target="_blank" rel="noopener me" '
                      f'aria-label="{rede.capitalize()}">{ICONES_REDE[rede]}</a>')
    if redes:
        redes = f'<div class="redes">{redes}</div>'

    c = cfg["contato"]
    linhas = []
    if preenchido(c.get("telefone")):
        tel = re.sub(r"\D", "", c.get("telefone_link") or c["telefone"])
        linhas.append(f'<li><a href="tel:+{tel}">{e(formatar_telefone_exibicao(c, ""))}</a></li>')
    if preenchido(c.get("email")):
        linhas.append(f'<li><a href="mailto:{e(c["email"])}">{e(c["email"])}</a></li>')
    cidade = ", ".join(x for x in [c.get("cidade"), c.get("estado")] if preenchido(x))
    if cidade:
        linhas.append(f"<li>{e(cidade)}, Brazil</li>")
    if preenchido(c.get("creci")):
        linhas.append(f'<li>CRECI {e(c["creci"])}</li>')

    return f"""<footer class="rodape">
  <div class="env">
    <div class="rodape__grade">
      <div>
        <a class="marca" href="/{lang}/" aria-label="{e(cfg['marca']['nome'])}">
          {SVG_SELO_RODAPE}
          <span class="marca__txt"><span class="marca__nome">{e(cfg['marca']['nome'])}</span></span>
        </a>
        <p class="rodape__sobre">{e(t['aviso_idioma'])}</p>
        {redes}
      </div>
      <div>
        <h4>{e(t['nav_titulo'])}</h4>
        <ul class="rodape__lista">{nav}</ul>
      </div>
      <div>
        <h4>{e(t['contato_titulo'])}</h4>
        <ul class="rodape__lista">{''.join(linhas) or '<li>—</li>'}</ul>
      </div>
      <div>
        <h4>{e(t['comunidade_titulo'])}</h4>
        <ul class="rodape__lista">
          <li><a href="/{lang}/blog/">{e(t['entrar_comunidade'])}</a></li>
          <li><a href="/{lang}/blog/">{e(t['noticias'])}</a></li>
          <li><a href="/{lang}/imoveis/">{e(t['imoveis'])}</a></li>
        </ul>
      </div>
    </div>
    <div class="rodape__base">
      <span>&copy; <span data-ano>{date.today().year}</span> {e(cfg['marca']['nome'])}. {e(t['direitos'])}</span>
    </div>
  </div>
</footer>"""


def gerar_datacenter_i18n(cfg: dict, s: dict, lang: str) -> str:
    """Gera as versões traduzidas (en/zh) da página de Data Center, com
    header/footer/nav próprios (traduzidos) e hreflang apontando pt/en/zh."""
    idioma_html = {"en": "en", "zh": "zh-Hans"}[lang]
    url_path = f"/{lang}/data-center/"
    zap = montar_url_zap(cfg)
    rotulos_botao = {
        "en": {"modelos": "See models and specs", "whatsapp": "Talk on WhatsApp now"},
        "zh": {"modelos": "查看模式与规格", "whatsapp": "立即通过WhatsApp咨询"},
    }[lang]

    botoes_hero = f'<a class="btn btn--dourado" href="#modelos">{rotulos_botao["modelos"]}</a>'
    if zap:
        botoes_hero += f'<a class="btn btn--claro" href="{e(zap)}" target="_blank" rel="noopener">{rotulos_botao["whatsapp"]}</a>'

    largura, altura = dimensoes_midia_url(s.get("foto_hero", ""), 1920, 1080)
    img_hero = (f'<img class="hero__foto" src="{e(s.get("foto_hero",""))}" alt="{e(s.get("chamada",""))}" '
                f'width="{largura}" height="{altura}" loading="eager" fetchpriority="high">')

    corpo = [f"""<section class="hero hero--interno">
  {img_hero}{SVG_HORIZONTE}
  <div class="env hero__int">
    <p class="olho">{e(s.get('olho',''))}</p>
    <h1>{e(s.get('chamada',''))}</h1>
    <p class="hero__texto">{e(s.get('hero_texto',''))}</p>
    <div class="grupo-btn">{botoes_hero}</div>
  </div>
</section>"""]

    pilares = "".join(
        f'<article class="card"><div class="card__num">{e(p.get("num",""))}</div>'
        f'<h3>{e(p.get("titulo",""))}</h3><p>{e(p.get("texto",""))}</p></article>'
        for p in s.get("pilares", [])
    )
    if pilares:
        corpo.append(f'<section class="secao secao--branca"><div class="env"><div class="grade grade--3">{pilares}</div></div></section>')

    galeria = s.get("galeria", [])
    if galeria:
        itens_galeria = "".join(
            f'<a class="galeria__link js-foto-modal" href="{e(g["foto"])}" '
            f'data-foto-modal-src="{e(g["foto"])}" '
            f'data-foto-modal-alt="{e(g.get("legenda",""))}" '
            f'title="Abrir foto no visualizador">'
            f'<img src="{e(g["foto"])}" alt="{e(g.get("legenda",""))}" '
            f'width="{(dim := dimensoes_midia_url(g["foto"], 1200, 800))[0]}" height="{dim[1]}" '
            f'loading="lazy" sizes="(max-width: 640px) 100vw, 50vw">'
            f'</a>'
            for g in galeria
        )
        corpo.append(f'<section class="secao secao--clara"><div class="env"><div class="galeria galeria--curada galeria--datacenter">{itens_galeria}</div></div></section>')

    modelos = s.get("modelos", [])
    if modelos:
        cards = "".join(
            f'<article class="card"><div class="card__num">{e(m.get("potencia",""))}</div>'
            f'<h3>{e(m.get("nome",""))}</h3><p>{e(m.get("desc",""))}</p>'
            f'<p class="link-seta" style="margin-top:1rem"><a class="link-seta" href="#modelo-{e(m.get("id",""))}">'
            f'{"See specifications" if lang=="en" else "查看详情"}</a></p></article>'
            for m in modelos
        )
        rotulos_campo = {
            "en": {"area": "Estimated land area", "racks": "Estimated rack capacity", "redundancia": "Redundancy",
                   "prazo": "Estimated delivery time", "publico": "Ideal for", "falar": "Talk about the"},
            "zh": {"area": "预估用地面积", "racks": "预估机架容量", "redundancia": "冗余等级",
                   "prazo": "预估交付周期", "publico": "适用对象", "falar": "咨询模式:"},
        }[lang]
        detalhes = ""
        for m in modelos:
            btn_modelo = ""
            if zap:
                btn_modelo = f'<a class="btn btn--dourado btn--bloco" href="{e(zap)}" target="_blank" rel="noopener">{rotulos_campo["falar"]} {e(m.get("nome",""))}</a>'
            detalhes += f"""<div class="painel" id="modelo-{e(m.get('id',''))}" style="position:static; margin-bottom:1.5rem; scroll-margin-top:100px;">
      <h3 style="margin-bottom:.3rem">{e(m.get('nome',''))}</h3>
      <p class="painel__preco-nota">{e(m.get('potencia',''))}</p>
      <ul class="painel__linhas">
        <li><span class="rot">{rotulos_campo['area']}</span><span class="val">{e(m.get('area',''))}</span></li>
        <li><span class="rot">{rotulos_campo['racks']}</span><span class="val">{e(m.get('racks',''))}</span></li>
        <li><span class="rot">{rotulos_campo['redundancia']}</span><span class="val">{e(m.get('redundancia',''))}</span></li>
        <li><span class="rot">{rotulos_campo['prazo']}</span><span class="val">{e(m.get('prazo',''))}</span></li>
        <li><span class="rot">{rotulos_campo['publico']}</span><span class="val" style="text-align:right; max-width:60%">{e(m.get('publico',''))}</span></li>
      </ul>
      {btn_modelo}
    </div>"""
        titulo_modelos = "Three reference scenarios — or a custom project" if lang == "en" else "三种参考方案——或定制项目"
        olho_modelos = "Models and specs" if lang == "en" else "模式与规格"
        corpo.append(f"""<section class="secao secao--branca" id="modelos">
  <div class="env">
    <div class="cabeca-secao cabeca-secao--centro"><p class="olho olho--centro">{olho_modelos}</p><h2>{titulo_modelos}</h2></div>
    <div class="grade grade--3">{cards}</div>
    <div style="margin-top:2.5rem">{detalhes}</div>
    <p class="nota-modelos" style="font-size:.85rem;color:var(--tinta-suave);margin-top:1.5rem;max-width:70ch">{e(s.get("nota_modelos",""))}</p>
  </div>
</section>""")

    faq = s.get("faq", [])
    if faq:
        faq_html = "".join(
            f'<details class="ficha-tecnica" style="margin-top:0"><summary class="ficha-tecnica__abrir">{e(qa.get("pergunta",""))}</summary>'
            f'<div class="ficha-tecnica__corpo"><p>{e(qa.get("resposta",""))}</p></div></details>'
            for qa in faq
        )
        olho_faq = "Frequently asked questions" if lang == "en" else "常见问题"
        titulo_faq = "Common questions about selling and structuring a Data Center" if lang == "en" else "关于数据中心销售与规划的常见问题"
        corpo.append(f"""<section class="secao">
  <div class="env">
    <div class="cabeca-secao cabeca-secao--centro"><p class="olho olho--centro">{olho_faq}</p><h2>{titulo_faq}</h2></div>
    {faq_html}
  </div>
</section>""")

    cta_botao_href = e(zap) if zap else "/contato/"
    cta_alvo = ' target="_blank" rel="noopener"' if zap else ""
    corpo.append(f"""<section class="cta-faixa">
  <div class="env cta-faixa__int">
    <h2>{e(s.get('cta_titulo',''))}</h2>
    <p>{e(s.get('cta_texto',''))}</p>
    <a class="btn btn--dourado" href="{cta_botao_href}"{cta_alvo}>{e(s.get('cta_botao',''))}</a>
  </div>
</section>""")

    modelos_schema = [
        {
            "@type": "Product", "name": m.get("nome", ""), "description": m.get("desc", ""),
            "additionalProperty": [
                {"@type": "PropertyValue", "name": "Power" if lang == "en" else "功率", "value": m.get("potencia", "")},
                {"@type": "PropertyValue", "name": "Estimated area" if lang == "en" else "预估面积", "value": m.get("area", "")},
                {"@type": "PropertyValue", "name": "Redundancy" if lang == "en" else "冗余", "value": m.get("redundancia", "")},
            ],
        } for m in modelos
    ]
    dominio = cfg["site"]["dominio"].rstrip("/")
    ld_service = json.dumps({
        "@context": "https://schema.org", "@type": "Service",
        "name": s.get("titulo", ""), "description": s.get("descricao_meta", s.get("chamada", "")),
        "inLanguage": idioma_html,
        "provider": {"@type": "RealEstateAgent", "name": cfg["marca"]["nome"], "url": dominio},
        "areaServed": [{"@type": "Country", "name": "Brazil"}, {"@type": "Place", "name": "Worldwide" if lang == "en" else "全球"}],
        **({"image": [{"@type": "ImageObject", "contentUrl": dominio + g["foto"],
                       "caption": g.get("legenda", ""),
                       "width": dimensoes_midia_url(g["foto"], 1200, 800)[0],
                       "height": dimensoes_midia_url(g["foto"], 1200, 800)[1]}
                      for g in galeria]} if galeria else {}),
        **({"hasOfferCatalog": {"@type": "OfferCatalog",
            "name": "Prime Fazendas Data Center models", "itemListElement": modelos_schema}} if modelos_schema else {}),
    }, ensure_ascii=False)

    ld_faq = ""
    if faq:
        ld_faq = json.dumps({
            "@context": "https://schema.org", "@type": "FAQPage", "inLanguage": idioma_html,
            "mainEntity": [
                {"@type": "Question", "name": qa.get("pergunta", ""),
                 "acceptedAnswer": {"@type": "Answer", "text": qa.get("resposta", "")}}
                for qa in faq
            ],
        }, ensure_ascii=False)

    breadcrumb_home = "Home" if lang == "en" else "首页"
    breadcrumb_dc = "Data Center"
    ld_migalha = json.dumps({
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": breadcrumb_home, "item": f"{dominio}/"},
            {"@type": "ListItem", "position": 2, "name": breadcrumb_dc, "item": f"{dominio}{url_path}"},
        ],
    }, ensure_ascii=False)

    hreflang = [
        ("pt-BR", f"{dominio}/data-center/"),
        ("en", f"{dominio}/en/data-center/"),
        ("zh-Hans", f"{dominio}/zh/data-center/"),
        ("x-default", f"{dominio}/data-center/"),
    ]

    ga = ""
    if preenchido(cfg.get("analytics", {}).get("ga4_id")):
        gid = e(cfg["analytics"]["ga4_id"])
        ga = (f'<script async src="https://www.googletagmanager.com/gtag/js?id={gid}"></script>\n'
              f'<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}'
              f"gtag('js',new Date());gtag('config','{gid}');</script>")

    zap_botao = ""
    if zap:
        zap_botao = f'<a class="zap" href="{e(zap)}" target="_blank" rel="noopener" aria-label="WhatsApp">{SVG_ZAP}</a>'

    titulo_completo = f"{s.get('titulo','')} | {cfg['marca']['nome']}"
    canonica = f"{dominio}{url_path}"
    hreflang_tags = "\n".join(f'<link rel="alternate" hreflang="{e(l)}" href="{e(h)}">' for l, h in hreflang)
    blocos_ld = [b for b in [ld_service, ld_faq, ld_migalha] if b]
    ld_html = "\n".join(f'<script type="application/ld+json">{b}</script>' for b in blocos_ld)

    return f"""<!DOCTYPE html>
<html lang="{e(idioma_html)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(titulo_completo)}</title>
<meta name="description" content="{e(s.get('descricao_meta',''))}">
<link rel="canonical" href="{e(canonica)}">
<meta name="robots" content="index, follow">
{hreflang_tags}
<meta name="theme-color" content="#0C1E33">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{e(cfg['marca']['nome'])}">
<meta property="og:title" content="{e(s.get('titulo',''))}">
<meta property="og:description" content="{e(s.get('descricao_meta',''))}">
<meta property="og:url" content="{e(canonica)}">
<meta property="og:locale" content="{e(idioma_html.replace('-','_'))}">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="/assets/favicon-32.png" sizes="32x32" type="image/png">
<link rel="icon" href="/assets/favicon-192.png" sizes="192x192" type="image/png">

<link rel="stylesheet" href="/assets/estilo.css">
{ld_html}
{ga}
<script defer src="/_vercel/insights/script.js"></script>
</head>
<body>
<a class="pular" href="#principal">{"Skip to content" if lang=="en" else "跳转到主要内容"}</a>
{cabecalho_i18n(cfg, lang, url_path)}
<main id="principal">
{chr(10).join(corpo)}
</main>
{rodape_i18n(cfg, lang)}
{zap_botao}
<script src="/assets/site.js" defer></script>
</body>
</html>
"""


def _skeleton_i18n(cfg: dict, lang: str, url_path: str, titulo: str, descricao_meta: str,
                    corpo_html: str, json_ld_list: list[str] | None = None) -> str:
    """Skeleton HTML reutilizavel para paginas institucionais traduzidas (home,
    sobre, servicos, contato, agenda-agro). Mesmo padrao de hreflang/idioma/schema
    usado em gerar_datacenter_i18n, generalizado para qualquer pagina simples."""
    idioma_html = {"en": "en", "zh": "zh-Hans"}[lang]
    dominio = cfg["site"]["dominio"].rstrip("/")
    pt_path = url_path  # url_path aqui é sempre o caminho em PT, ex: "/sobre/"
    hreflang = [
        ("pt-BR", f"{dominio}{pt_path}"),
        ("en", f"{dominio}/en{pt_path}" if pt_path != "/" else f"{dominio}/en/"),
        ("zh-Hans", f"{dominio}/zh{pt_path}" if pt_path != "/" else f"{dominio}/zh/"),
        ("x-default", f"{dominio}{pt_path}"),
    ]
    canonica = f"{dominio}/{lang}{pt_path}" if pt_path != "/" else f"{dominio}/{lang}/"
    hreflang_tags = "\n".join(f'<link rel="alternate" hreflang="{e(l)}" href="{e(h)}">' for l, h in hreflang)
    blocos_ld = json_ld_list or []
    ld_html = "\n".join(f'<script type="application/ld+json">{b}</script>' for b in blocos_ld if b)
    ga = ""
    if preenchido(cfg.get("analytics", {}).get("ga4_id")):
        gid = e(cfg["analytics"]["ga4_id"])
        ga = (f'<script async src="https://www.googletagmanager.com/gtag/js?id={gid}"></script>\n'
              f'<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}'
              f"gtag('js',new Date());gtag('config','{gid}');</script>")
    zap = montar_url_zap(cfg)
    zap_botao = ""
    if zap:
        zap_botao = f'<a class="zap" href="{e(zap)}" target="_blank" rel="noopener" aria-label="WhatsApp">{SVG_ZAP}</a>'
    titulo_completo = f"{titulo} | {cfg['marca']['nome']}"
    url_atual_i18n = f"/{lang}{pt_path}" if pt_path != "/" else f"/{lang}/"

    return f"""<!DOCTYPE html>
<html lang="{e(idioma_html)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(titulo_completo)}</title>
<meta name="description" content="{e(descricao_meta)}">
<link rel="canonical" href="{e(canonica)}">
<meta name="robots" content="index, follow">
{hreflang_tags}
<meta name="theme-color" content="#0C1E33">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{e(cfg['marca']['nome'])}">
<meta property="og:title" content="{e(titulo)}">
<meta property="og:description" content="{e(descricao_meta)}">
<meta property="og:url" content="{e(canonica)}">
<meta property="og:locale" content="{e(idioma_html.replace('-','_'))}">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="/assets/favicon-32.png" sizes="32x32" type="image/png">
<link rel="icon" href="/assets/favicon-192.png" sizes="192x192" type="image/png">

<link rel="stylesheet" href="/assets/estilo.css">
{ld_html}
{ga}
<script defer src="/_vercel/insights/script.js"></script>
</head>
<body>
<a class="pular" href="#principal">{"Skip to content" if lang=="en" else "跳转到主要内容"}</a>
{cabecalho_i18n(cfg, lang, url_atual_i18n)}
<main id="principal">
{corpo_html}
</main>
{rodape_i18n(cfg, lang)}
{zap_botao}
<script src="/assets/site.js" defer></script>
</body>
</html>
"""


def gerar_home_i18n(cfg: dict, s: dict, lang: str) -> str:
    zap = montar_url_zap(cfg)
    botoes = f'<a class="btn btn--dourado" href="/imoveis/">{e(s.get("hero_cta",""))}</a>'
    if zap:
        botoes += f'<a class="btn btn--claro" href="{e(zap)}" target="_blank" rel="noopener">{e(s.get("hero_cta_secundario",""))}</a>'
    largura, altura = dimensoes_midia_url("/midia/imoveis/fazenda-amazonita/aerea-02.jpg", 1920, 1080)
    img = (f'<img class="hero__foto" src="/midia/imoveis/fazenda-amazonita/aerea-02.jpg" alt="{e(s.get("hero_titulo",""))}" '
           f'width="{largura}" height="{altura}" loading="eager" fetchpriority="high">')
    corpo = [f"""<section class="hero">
  {img}{SVG_HORIZONTE}
  <div class="env hero__int">
    <h1>{e(s.get('hero_titulo',''))}</h1>
    <p class="hero__texto">{e(s.get('hero_texto',''))}</p>
    <div class="grupo-btn">{botoes}</div>
  </div>
</section>"""]

    pilares = "".join(
        f'<article class="card"><h3>{e(p.get("titulo",""))}</h3><p>{e(p.get("texto",""))}</p></article>'
        for p in s.get("pilares", [])
    )
    if pilares:
        corpo.append(f'<section class="secao secao--branca"><div class="env"><div class="grade grade--2">{pilares}</div></div></section>')

    corpo.append(cta_faixa_i18n(cfg, s.get("faixa_titulo", ""), s.get("faixa_texto", ""),
                                 "Talk to a specialist" if lang == "en" else "联系专业顾问", lang))

    ld = json.dumps({
        "@context": "https://schema.org", "@type": "RealEstateAgent", "inLanguage": {"en": "en", "zh": "zh-Hans"}[lang],
        "name": cfg["marca"]["nome"], "url": cfg["site"]["dominio"],
        "description": s.get("hero_texto", ""),
        "areaServed": {"@type": "State", "name": "Tocantins"},
    }, ensure_ascii=False)

    titulo = {"en": "Prime Fazendas — Farms and rural properties in Tocantins",
              "zh": "Prime Fazendas — 托坎廷斯州农场与乡村地产"}[lang]
    return _skeleton_i18n(cfg, lang, "/", titulo, s.get("hero_texto", ""), "\n".join(corpo), [ld])


def gerar_sobre_i18n(cfg: dict, s: dict, lang: str) -> str:
    quem_somos = paragrafos(s.get("quem_somos"))
    historia = paragrafos(s.get("historia"))
    diferenciais = "".join(
        f'<article class="card"><h3>{e(d.get("titulo",""))}</h3><p>{e(d.get("texto",""))}</p></article>'
        for d in s.get("diferenciais", [])
    )
    valores = "".join(f"<li>{e(v)}</li>" for v in s.get("valores", []))

    corpo = [f"""<section class="hero hero--interno">
  <div class="env hero__int"><h1>{e(s.get('titulo',''))}</h1><p class="hero__texto">{e(s.get('chamada',''))}</p></div>
</section>
<section class="secao"><div class="env"><div class="prosa">{quem_somos}</div></div></section>"""]

    if historia:
        corpo.append(f'<section class="secao secao--clara"><div class="env"><h2>{e(s.get("historia_titulo",""))}</h2><div class="prosa">{historia}</div></div></section>')

    if diferenciais:
        corpo.append(f"""<section class="secao"><div class="env">
  <div class="cabeca-secao"><h2>{e(s.get("diferenciais_titulo",""))}</h2><p class="chamada">{e(s.get("diferenciais_texto",""))}</p></div>
  <div class="grade grade--2">{diferenciais}</div>
</div></section>""")

    parceiros_lista = s.get("parceiros", [])
    if parceiros_lista:
        parceiros_cards = "".join(
            f'<article class="card"><h3>{e(pnr.get("nome",""))}</h3><p>{e(pnr.get("texto",""))}</p></article>'
            for pnr in parceiros_lista
        )
        olho_parceiros = "Partners" if lang == "en" else "合作伙伴"
        corpo.append(f"""<section class="secao secao--clara"><div class="env">
  <div class="cabeca-secao"><p class="olho">{olho_parceiros}</p><h2>{e(s.get("parceiros_titulo",""))}</h2><p class="chamada">{e(s.get("parceiros_intro",""))}</p></div>
  <div class="grade grade--2">{parceiros_cards}</div>
</div></section>""")

    corpo.append(f"""<section class="secao secao--escura"><div class="env">
  <div class="grade grade--2" style="align-items:start">
    <div><h2>{"Mission" if lang=="en" else "使命"}</h2><p class="chamada">{e(s.get("missao",""))}</p></div>
    <div><p class="olho">{"Values" if lang=="en" else "价值观"}</p><ul class="marcada marcada--check">{valores}</ul></div>
  </div>
</div></section>""")

    corpo.append(cta_faixa_i18n(cfg, "Want to know our portfolio?" if lang == "en" else "想了解我们的项目库吗?",
                                 "" , "See properties" if lang == "en" else "查看房产项目", lang, href="/imoveis/"))

    ld = json.dumps({
        "@context": "https://schema.org", "@type": "AboutPage", "inLanguage": {"en": "en", "zh": "zh-Hans"}[lang],
        "name": s.get("titulo", ""),
        "mainEntity": {"@type": "Organization", "name": cfg["marca"]["nome"], "url": cfg["site"]["dominio"]},
    }, ensure_ascii=False)

    ld_migalha = ld_breadcrumbs_i18n(cfg, lang, [({"en": "About Us", "zh": "关于我们"}[lang], f"/{lang}/sobre/")])
    return _skeleton_i18n(cfg, lang, "/sobre/", s.get("titulo", ""), s.get("descricao_meta", ""), "\n".join(corpo), [ld, ld_migalha])


def gerar_servicos_i18n(cfg: dict, s: dict, lang: str) -> str:
    cards = "".join(
        f'<article class="card"><div class="card__num">{numeral_romano(i+1)}</div><h3>{e(x["titulo"])}</h3><p>{e(x["texto"])}</p></article>'
        for i, x in enumerate(s.get("lista", []))
    )
    corpo = [f"""<section class="hero hero--interno">
  <div class="env hero__int"><h1>{e(s.get('titulo',''))}</h1><p class="hero__texto">{e(s.get('chamada',''))}</p></div>
</section>
<section class="secao"><div class="env"><div class="grade grade--2">{cards}</div></div></section>"""]

    corpo.append(cta_faixa_i18n(cfg, s.get("cta_titulo", ""), s.get("cta_texto", ""), s.get("cta_botao", ""), lang))

    ld = json.dumps({
        "@context": "https://schema.org", "@type": "Service", "inLanguage": {"en": "en", "zh": "zh-Hans"}[lang],
        "name": s.get("titulo", ""), "description": s.get("chamada", ""),
        "provider": {"@type": "RealEstateAgent", "name": cfg["marca"]["nome"], "url": cfg["site"]["dominio"]},
        **({"hasOfferCatalog": {"@type": "OfferCatalog", "name": "Prime Fazendas services",
            "itemListElement": [{"@type": "Offer", "itemOffered": {"@type": "Service", "name": x["titulo"], "description": x.get("texto","")}} for x in s.get("lista", [])]}} if s.get("lista") else {}),
    }, ensure_ascii=False)

    ld_migalha = ld_breadcrumbs_i18n(cfg, lang, [({"en": "Services", "zh": "服务项目"}[lang], f"/{lang}/servicos/")])
    return _skeleton_i18n(cfg, lang, "/servicos/", s.get("titulo", ""), s.get("descricao_meta", ""), "\n".join(corpo), [ld, ld_migalha])


TEXTOS_CONTATO_I18N = {
    "en": {
        "nome": "Name", "email": "Email", "telefone": "Phone / WhatsApp",
        "interesse": "What are you looking for", "opcoes_interesse": [
            "Buy a property", "Sell my property", "Lease a property (looking for land)",
            "I have a property and want to offer it for lease", "Appraise a property",
            "Land / environmental regularization", "Invest in agribusiness", "Other",
        ],
        "regiao": "Region of interest", "regiao_placeholder": "e.g. Palmas, Matopiba, Araguaia Valley",
        "empresa": "Company / Group (if applicable)", "empresa_placeholder": "Company or group name, if any",
        "area_pretendida": "Desired or available area (ha)", "area_placeholder": "e.g. 500 to 2,000 ha",
        "investimento": "Investment range", "opcoes_investimento": [
            "Prefer not to say", "Up to US$ 1 million", "US$ 1 to 4 million",
            "US$ 4 to 10 million", "Above US$ 10 million",
        ],
        "mensagem": "Message", "mensagem_placeholder": "Tell us what you're looking for: size, suitability, region, timeline.",
        "enviar": "Send and talk on WhatsApp",
        "confirmacao": ("We've received your details and opened WhatsApp with your message ready. "
                        "One of our consultants will contact you shortly. If WhatsApp didn't open, "
                        "check your pop-up blocker."),
        "canais": "Direct channels", "onde_estamos": "Where we are", "atendimento": "Hours",
    },
    "zh": {
        "nome": "\u59d3\u540d", "email": "\u90ae\u7bb1", "telefone": "\u7535\u8bdd/WhatsApp",
        "interesse": "\u60a8\u60f3\u54a8\u8be2\u7684\u4e8b\u9879", "opcoes_interesse": [
            "\u8d2d\u4e70\u623f\u4ea7", "\u51fa\u552e\u6211\u7684\u623f\u4ea7",
            "\u79df\u8d41\u571f\u5730\uff08\u5bfb\u627e\u571f\u5730\uff09",
            "\u6211\u6709\u4e00\u5904\u623f\u4ea7\u60f3\u51fa\u79df",
            "\u8bc4\u4f30\u623f\u4ea7", "\u571f\u5730/\u73af\u5883\u5408\u89c4\u767b\u8bb0",
            "\u6295\u8d44\u519c\u4e1a", "\u5176\u4ed6",
        ],
        "regiao": "\u610f\u5411\u5730\u533a", "regiao_placeholder": "\u4f8b\u5982\uff1a\u5e15\u5c14\u9a6c\u65af\u3001\u9a6c\u6258\u76ae\u5df4\u3001\u963f\u62c9\u74dc\u4e9a\u6cb3\u8c37",
        "empresa": "\u516c\u53f8/\u673a\u6784\uff08\u5982\u9002\u7528\uff09", "empresa_placeholder": "\u516c\u53f8\u6216\u673a\u6784\u540d\u79f0\uff08\u5982\u6709\uff09",
        "area_pretendida": "\u610f\u5411\u6216\u53ef\u552e\u9762\u79ef\uff08\u516c\u9877\uff09", "area_placeholder": "\u4f8b\u5982\uff1a500\u81f32,000\u516c\u9877",
        "investimento": "\u6295\u8d44\u91d1\u989d\u533a\u95f4", "opcoes_investimento": [
            "\u4e0d\u613f\u900f\u9732", "100\u4e07\u7f8e\u5143\u4ee5\u4e0b", "100\u81f3400\u4e07\u7f8e\u5143",
            "400\u81f31000\u4e07\u7f8e\u5143", "1000\u4e07\u7f8e\u5143\u4ee5\u4e0a",
        ],
        "mensagem": "\u7559\u8a00", "mensagem_placeholder": "\u8bf7\u544a\u8bc9\u6211\u4eec\u60a8\u7684\u9700\u6c42\uff1a\u9762\u79ef\u3001\u7528\u9014\u3001\u5730\u533a\u3001\u65f6\u95f4\u8981\u6c42\u3002",
        "enviar": "\u53d1\u9001\u5e76\u524d\u5f80WhatsApp\u54a8\u8be2",
        "confirmacao": ("\u6211\u4eec\u5df2\u6536\u5230\u60a8\u7684\u4fe1\u606f\uff0c\u5e76\u4e3a\u60a8\u6253\u5f00\u4e86WhatsApp\uff0c"
                        "\u6d88\u606f\u5df2\u51c6\u5907\u597d\u3002\u6211\u4eec\u7684\u987e\u95ee\u4f1a\u5c3d\u5feb\u4e0e\u60a8\u8054\u7cfb\u3002"
                        "\u5982\u679cWhatsApp\u672a\u80fd\u6253\u5f00\uff0c\u8bf7\u68c0\u67e5\u60a8\u7684\u5f39\u7a97\u62e6\u622a\u8bbe\u7f6e\u3002"),
        "canais": "\u76f4\u63a5\u8054\u7cfb\u65b9\u5f0f", "onde_estamos": "\u6211\u4eec\u7684\u4f4d\u7f6e", "atendimento": "\u670d\u52a1\u65f6\u95f4",
    },
}


def gerar_contato_i18n(cfg: dict, s: dict, lang: str) -> str:
    tx = TEXTOS_CONTATO_I18N[lang]
    c = cfg["contato"]

    numero_zap = re.sub(r"\D", "", str(c.get("whatsapp_numero_internacional") or "")) \
        if preenchido(c.get("whatsapp_numero_internacional")) else ""
    endpoint_lead = cfg.get("formulario", {}).get("endpoint", "")

    opcoes_interesse = "".join(f"<option>{e(o)}</option>" for o in tx["opcoes_interesse"])
    opcoes_investimento = "".join(f"<option>{e(o)}</option>" for o in tx["opcoes_investimento"])

    form = f"""<form class="form" data-modo="whatsapp" data-whatsapp="{e(numero_zap)}"{f' data-endpoint="{e(endpoint_lead)}"' if preenchido(endpoint_lead) else ''} data-msg-sucesso="{e(tx['confirmacao'])}">
  <input type="text" name="_honey" style="display:none" tabindex="-1" autocomplete="off">
  <input type="hidden" name="_subject" value="Novo lead — site Prime Fazendas ({lang.upper()})">
  <input type="hidden" name="_template" value="table">
  <input type="hidden" name="_captcha" value="false">
  <div class="campo--duplo">
    <div class="campo">
      <label for="nome-{lang}">{e(tx['nome'])} <span class="req">*</span></label>
      <input type="text" id="nome-{lang}" name="nome" required autocomplete="name">
    </div>
    <div class="campo">
      <label for="email-{lang}">{e(tx['email'])} <span class="req">*</span></label>
      <input type="email" id="email-{lang}" name="email" required autocomplete="email">
    </div>
  </div>
  <div class="campo">
    <label for="telefone-{lang}">{e(tx['telefone'])}</label>
    <input type="tel" id="telefone-{lang}" name="telefone" autocomplete="tel">
  </div>
  <div class="campo--duplo">
    <div class="campo">
      <label for="interesse-{lang}">{e(tx['interesse'])}</label>
      <select id="interesse-{lang}" name="interesse">{opcoes_interesse}</select>
    </div>
    <div class="campo">
      <label for="regiao-{lang}">{e(tx['regiao'])}</label>
      <input type="text" id="regiao-{lang}" name="regiao" placeholder="{e(tx['regiao_placeholder'])}">
    </div>
  </div>
  <div class="campo--duplo">
    <div class="campo">
      <label for="empresa-{lang}">{e(tx['empresa'])}</label>
      <input type="text" id="empresa-{lang}" name="empresa" placeholder="{e(tx['empresa_placeholder'])}">
    </div>
    <div class="campo">
      <label for="area_pretendida-{lang}">{e(tx['area_pretendida'])}</label>
      <input type="text" id="area_pretendida-{lang}" name="area_pretendida" placeholder="{e(tx['area_placeholder'])}">
    </div>
  </div>
  <div class="campo">
    <label for="investimento-{lang}">{e(tx['investimento'])}</label>
    <select id="investimento-{lang}" name="investimento">{opcoes_investimento}</select>
  </div>
  <div class="campo">
    <label for="mensagem-{lang}">{e(tx['mensagem'])}</label>
    <textarea id="mensagem-{lang}" name="mensagem" placeholder="{e(tx['mensagem_placeholder'])}"></textarea>
  </div>
  <div class="grupo-btn">
    <button class="btn btn--principal" type="submit">{e(tx['enviar'])}</button>
  </div>
  <p class="form__nota">{e(s.get('form_nota', ''))}</p>
  <p class="form__nota" data-retorno hidden role="status"></p>
</form>"""

    itens = []
    if preenchido(c.get("telefone")):
        tel = re.sub(r"\D", "", c.get("telefone_link") or c["telefone"])
        itens.append((tx["telefone"], f'<a href="tel:+{tel}">{e(formatar_telefone_exibicao(c, ""))}</a>'))
    if preenchido(c.get("email")):
        itens.append((tx["email"], f'<a href="mailto:{e(c["email"])}">{e(c["email"])}</a>'))
    if preenchido(c.get("endereco")):
        itens.append(("Address" if lang == "en" else "\u5730\u5740", e(c["endereco"])))
    cidade = ", ".join(x for x in [c.get("cidade"), c.get("estado")] if preenchido(x))
    if cidade:
        itens.append((tx["onde_estamos"], e(cidade)))
    if preenchido(c.get("horario")):
        itens.append((tx["atendimento"], e(c["horario"])))

    lado = "".join(
        f'<div class="contato-item"><p class="contato-item__rot">{e(r)}</p>'
        f'<p class="contato-item__val">{v}</p></div>'
        for r, v in itens
    )

    corpo = [f"""<section class="hero hero--interno">
  <div class="env hero__int"><h1>{e(s.get('titulo',''))}</h1><p class="hero__texto">{e(s.get('chamada',''))}</p></div>
</section>
<section class="secao">
  <div class="env">
    <div class="contato-grade">
      <div>
        <h2>{e(s.get('form_titulo',''))}</h2>
        <p class="chamada chamada--larga" style="margin-bottom:2.25rem">{e(s.get('intro', ''))}</p>
        {form}
      </div>
      <div>
        <p class="olho">{e(tx['canais'])}</p>
        {lado}
      </div>
    </div>
  </div>
</section>"""]

    ld = json.dumps({
        "@context": "https://schema.org", "@type": "ContactPage", "inLanguage": {"en": "en", "zh": "zh-Hans"}[lang],
        "name": s.get("titulo", ""),
    }, ensure_ascii=False)

    ld_migalha = ld_breadcrumbs_i18n(cfg, lang, [({"en": "Contact", "zh": "联系我们"}[lang], f"/{lang}/contato/")])
    return _skeleton_i18n(cfg, lang, "/contato/", s.get("titulo", ""), s.get("descricao_meta", ""), "\n".join(corpo), [ld, ld_migalha])


def gerar_agenda_agro_i18n(cfg: dict, s: dict, lang: str) -> str:
    corpo = [f"""<section class="hero hero--interno">
  <div class="env hero__int"><h1>{e(s.get('titulo',''))}</h1><p class="hero__texto">{e(s.get('chamada',''))}</p></div>
</section>
<section class="secao"><div class="env">
  <div class="cabeca-secao cabeca-secao--centro">
    <p class="olho olho--centro">{e(s.get('vazio_titulo',''))}</p>
    <p class="chamada">{e(s.get('vazio_texto',''))}</p>
  </div>
</div></section>"""]
    ld_migalha = ld_breadcrumbs_i18n(cfg, lang, [({"en": "Agro Calendar", "zh": "农业日历"}[lang], f"/{lang}/agenda-agro/")])
    return _skeleton_i18n(cfg, lang, "/agenda-agro/", s.get("titulo", ""), s.get("descricao_meta", ""), "\n".join(corpo), [ld_migalha])


def cta_faixa_i18n(cfg: dict, titulo: str, texto: str, botao: str, lang: str, href: str | None = None) -> str:
    zap = montar_url_zap(cfg)
    url = href or (zap if zap else "/contato/")
    alvo = ' target="_blank" rel="noopener"' if (not href and zap) else ""
    return f"""<section class="cta-faixa">
  <div class="env cta-faixa__int">
    <h2>{e(titulo)}</h2>
    {f'<p>{e(texto)}</p>' if texto else ''}
    <a class="btn btn--dourado" href="{e(url)}"{alvo}>{e(botao)}</a>
  </div>
</section>"""


def gerar_investir(cfg, pag, dados_agro) -> str:
    s = pag.get("investir", {})
    corpo = [hero(cfg, olho="Investir no agro", titulo=s.get("titulo", ""),
                  texto=s.get("chamada", ""), interno=True, foto="/midia/imoveis/fazenda-diamante-do-cerrado/foto-03.jpg")]

    corpo.append(f"""<section class="secao">
  <div class="env"><div class="prosa">{paragrafos(s.get('intro'))}</div></div>
</section>""")

    args = "".join(
        f'<article class="card"><h3>{e(a["titulo"])}</h3><p>{e(a["texto"])}</p></article>'
        for a in dados_agro.get("argumentos_investimento", [])
    )
    if args:
        corpo.append(f"""<section class="secao secao--clara">
  <div class="env">
    <div class="cabeca-secao"><p class="olho">A tese</p><h2>Por que terra agrícola</h2></div>
    <div class="grade grade--2">{args}</div>
  </div>
</section>""")

    indics = [i for i in dados_agro.get("indicadores", []) if not i.get("verificar")]
    if indics:
        blocos = ""
        for i in indics:
            fonte = f'{e(i.get("fonte", ""))} · {e(i.get("ano", ""))}'
            if preenchido(i.get("url")):
                fonte = f'<a href="{e(i["url"])}" target="_blank" rel="noopener">{fonte}</a>'
            blocos += (f'<div class="indic"><span class="indic__valor">{e(i.get("valor", ""))}</span>'
                       f'<p class="indic__rotulo">{e(i.get("rotulo", ""))}</p>'
                       f'<p class="indic__fonte">{fonte}</p></div>')
        corpo.append(f'<section class="secao secao--escura"><div class="env">'
                     f'<div class="grade grade--3">{blocos}</div></div></section>')

    fatores_brutos = dados_agro.get("fatores_regiao", [])
    if fatores_brutos:
        painel_fatores = []
        for i, fator in enumerate(fatores_brutos):
            titulo_fator, resumo_fator = resumo_fator_regiao(fator, i + 1)
            painel_fatores.append(
                f'<article class="territorio-card">'
                f'<p class="territorio-card__num">{i + 1:02d}</p>'
                f'<h3>{e(titulo_fator)}</h3>'
                f'<p>{e(resumo_fator)}</p>'
                f'</article>'
            )

        corpo.append(f"""<section class="secao">
  <div class="env">
    <div class="cabeca-secao">
      <p class="olho">A região</p>
      <h2>{e(s.get('regiao_titulo', 'Tocantins e Matopiba: leitura de território'))}</h2>
      <p class="chamada chamada--larga">{e(s.get('regiao_subtitulo', 'Em vez de um mapa genérico, mostramos um painel visual de leitura de mercado: logística, aptidão produtiva, custo de entrada e documentação.'))}</p>
    </div>
    <div class="territorio">
      <div class="territorio__mapa" aria-hidden="true">
        <span class="territorio__tag territorio__tag--secundaria">MATOPIBA</span>
        <span class="territorio__tag">Tocantins</span>
        <strong class="territorio__titulo">Posição estratégica</strong>
        <p class="territorio__texto">Leitura combinada de logística, mercado e segurança documental.</p>
        <div class="territorio__chip-list">
          <span class="territorio__chip">Arco Norte</span>
          <span class="territorio__chip">Due diligence</span>
          <span class="territorio__chip">Preço sob confirmação</span>
        </div>
      </div>
      <div class="grade grade--2">{''.join(painel_fatores)}</div>
    </div>
  </div>
</section>""")

    corpo.append(f"""<section class="secao secao--clara">
  <div class="env"><div class="prosa">
    <p class="olho">Atenção</p>
    <h2>{e(s.get('fechamento_titulo', ''))}</h2>
    {paragrafos(s.get('fechamento_texto'))}
  </div></div>
</section>""")

    faq = s.get("faq", [])
    if faq:
        faq_html = "".join(
            f'<details class="ficha-tecnica" style="margin-top:0"><summary class="ficha-tecnica__abrir">{e(qa.get("pergunta",""))}</summary>'
            f'<div class="ficha-tecnica__corpo"><p>{e(qa.get("resposta",""))}</p></div></details>'
            for qa in faq
        )
        corpo.append(f"""<section class="secao">
  <div class="env">
    <div class="cabeca-secao cabeca-secao--centro">
      <p class="olho olho--centro">Perguntas frequentes</p>
      <h2>Dúvidas comuns de quem está comprando terra rural</h2>
    </div>
    {faq_html}
  </div>
</section>""")

    corpo.append(cta_faixa(cfg, "Quer avaliar uma oportunidade?",
                           "Analisamos a propriedade — solo, documentação, passivo e preço — antes de você comprometer capital."))

    ld_migalha = ld_breadcrumbs(cfg, [("Início", "/"), ("Investir no Agro", "/investir-no-agro/")])
    ld_faq = json.dumps({
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": qa.get("pergunta", ""),
             "acceptedAnswer": {"@type": "Answer", "text": qa.get("resposta", "")}}
            for qa in faq
        ],
    }, ensure_ascii=False) if faq else ""

    return pagina(cfg, titulo=s.get("titulo", "Por que investir no agronegócio"),
                  descricao=s.get("descricao_meta", s.get("chamada", "")), url="/investir-no-agro/",
                  corpo="\n".join(corpo), json_ld=[b for b in [ld_migalha, ld_faq] if b],
                  hreflang=hreflang_para(cfg, "/investir-no-agro/"))


def gerar_investir_i18n(cfg: dict, s: dict, lang: str, dados_agro: dict) -> str:
    idioma_html = {"en": "en", "zh": "zh-Hans"}[lang]
    tx = {
        "en": {"tese_olho": "The thesis", "tese_titulo": "Why farmland",
               "regiao_olho": "The region", "atencao": "Attention",
               "cta_titulo": "Want to evaluate an opportunity?",
               "cta_texto": "We review the property — soil, documentation, liabilities and price — before you commit capital.",
               "cta_botao": "Talk to a specialist", "breadcrumb_home": "Home", "breadcrumb_pagina": "Invest in Agribusiness"},
        "zh": {"tese_olho": "投资逻辑", "tese_titulo": "为什么选择农地",
               "regiao_olho": "区域", "atencao": "注意事项",
               "cta_titulo": "想评估一个投资机会吗？",
               "cta_texto": "在您投入资金之前,我们会先审查物业——土壤、文件资料、潜在风险及价格。",
               "cta_botao": "联系专家", "breadcrumb_home": "首页", "breadcrumb_pagina": "投资农业"},
    }[lang]

    corpo = [f"""<section class="hero hero--interno">
  <div class="env hero__int"><h1>{e(s.get('titulo',''))}</h1><p class="hero__texto">{e(s.get('chamada',''))}</p></div>
</section>
<section class="secao"><div class="env"><div class="prosa">{paragrafos(s.get('intro'))}</div></div></section>"""]

    args = "".join(
        f'<article class="card"><h3>{e(a["titulo"])}</h3><p>{e(a["texto"])}</p></article>'
        for a in dados_agro.get("argumentos_investimento", [])
    )
    if args:
        corpo.append(f"""<section class="secao secao--clara">
  <div class="env">
    <div class="cabeca-secao"><p class="olho">{e(tx['tese_olho'])}</p><h2>{e(tx['tese_titulo'])}</h2></div>
    <div class="grade grade--2">{args}</div>
  </div>
</section>""")

    indics = [i for i in dados_agro.get("indicadores", []) if not i.get("verificar")]
    if indics:
        blocos = ""
        for i in indics:
            fonte = f'{e(i.get("fonte", ""))} · {e(i.get("ano", ""))}'
            if preenchido(i.get("url")):
                fonte = f'<a href="{e(i["url"])}" target="_blank" rel="noopener">{fonte}</a>'
            blocos += (f'<div class="indic"><span class="indic__valor">{e(i.get("valor", ""))}</span>'
                       f'<p class="indic__rotulo">{e(i.get("rotulo", ""))}</p>'
                       f'<p class="indic__fonte">{fonte}</p></div>')
        corpo.append(f'<section class="secao secao--escura"><div class="env">'
                     f'<div class="grade grade--3">{blocos}</div></div></section>')

    fatores_brutos = dados_agro.get("fatores_regiao", [])
    if fatores_brutos:
        painel_fatores = []
        for i, fator in enumerate(fatores_brutos):
            titulo_fator, resumo_fator = resumo_fator_regiao(fator, i + 1, lang)
            painel_fatores.append(
                f'<article class="territorio-card">'
                f'<p class="territorio-card__num">{numeral_romano(i + 1)}</p>'
                f'<h3>{e(titulo_fator)}</h3>'
                f'<p>{e(resumo_fator)}</p>'
                f'</article>'
            )
        corpo.append(f"""<section class="secao">
  <div class="env">
    <div class="cabeca-secao">
      <p class="olho">{e(tx['regiao_olho'])}</p>
      <h2>{e(s.get('regiao_titulo', ''))}</h2>
      <p class="chamada chamada--larga">{e(s.get('regiao_subtitulo', ''))}</p>
    </div>
    <div class="territorio">
      <div class="territorio__mapa" aria-hidden="true">
        <span class="territorio__tag territorio__tag--secundaria">MATOPIBA</span>
        <span class="territorio__tag">Tocantins</span>
        <strong class="territorio__titulo">Strategic position</strong>
        <p class="territorio__texto">Combined reading of logistics, market and legal security.</p>
        <div class="territorio__chip-list">
          <span class="territorio__chip">Arco Norte</span>
          <span class="territorio__chip">Due diligence</span>
          <span class="territorio__chip">Price on request</span>
        </div>
      </div>
      <div class="grade grade--2">{''.join(painel_fatores)}</div>
    </div>
  </div>
</section>""")

    corpo.append(f"""<section class="secao secao--clara">
  <div class="env"><div class="prosa">
    <p class="olho">{e(tx['atencao'])}</p>
    <h2>{e(s.get('fechamento_titulo', ''))}</h2>
    {paragrafos(s.get('fechamento_texto'))}
  </div></div>
</section>""")

    faq = s.get("faq", [])
    if faq:
        faq_titulo = "Frequently asked questions" if lang == "en" else "常见问题"
        faq_sub = ("Common questions from people buying rural land" if lang == "en"
                   else "购买农地时的常见问题")
        faq_html = "".join(
            f'<details class="ficha-tecnica" style="margin-top:0"><summary class="ficha-tecnica__abrir">{e(qa.get("pergunta",""))}</summary>'
            f'<div class="ficha-tecnica__corpo"><p>{e(qa.get("resposta",""))}</p></div></details>'
            for qa in faq
        )
        corpo.append(f"""<section class="secao">
  <div class="env">
    <div class="cabeca-secao cabeca-secao--centro">
      <p class="olho olho--centro">{e(faq_titulo)}</p>
      <h2>{e(faq_sub)}</h2>
    </div>
    {faq_html}
  </div>
</section>""")

    corpo.append(cta_faixa_i18n(cfg, tx["cta_titulo"], tx["cta_texto"], tx["cta_botao"], lang))

    ld = json.dumps({
        "@context": "https://schema.org", "@type": "WebPage", "inLanguage": idioma_html,
        "name": s.get("titulo", ""), "description": s.get("descricao_meta", ""),
    }, ensure_ascii=False)
    ld_faq = json.dumps({
        "@context": "https://schema.org", "@type": "FAQPage", "inLanguage": idioma_html,
        "mainEntity": [
            {"@type": "Question", "name": qa.get("pergunta", ""),
             "acceptedAnswer": {"@type": "Answer", "text": qa.get("resposta", "")}}
            for qa in faq
        ],
    }, ensure_ascii=False) if faq else ""

    ld_migalha = ld_breadcrumbs_i18n(cfg, lang, [({"en": "Invest in Agribusiness", "zh": "投资农业"}[lang], f"/{lang}/investir-no-agro/")])
    return _skeleton_i18n(cfg, lang, "/investir-no-agro/", s.get("titulo", ""), s.get("descricao_meta", ""),
                          "\n".join(corpo), [b for b in [ld, ld_faq, ld_migalha] if b])


def gerar_lista_imoveis(cfg, pag, imoveis) -> str:
    s = pag.get("imoveis", {})
    corpo = [hero(cfg, olho="Portfólio", titulo=s.get("titulo", "Imóveis rurais à venda"),
                  texto=s.get("chamada", ""), interno=True, foto="/midia/imoveis/fazenda-perola-do-leste/foto-03.jpg")]
    corpo.append("""<section class="secao secao--compacta">
  <div class="env">
    <div class="painel__alerta" style="margin:0">
      Preços, área e disponibilidade são confirmados antes da publicação. Se a propriedade
      estiver reservada ou em negociação, ela não aparece como disponível.
    </div>
  </div>
</section>""")


    if imoveis:
        tipos_presentes = []
        for i in imoveis:
            if i.get("tipo") and i["tipo"] not in tipos_presentes:
                tipos_presentes.append(i["tipo"])

        filtros = '<button class="filtro" data-filtro="todos" aria-pressed="true">Todas</button>'
        for t in tipos_presentes:
            filtros += (f'<button class="filtro" data-filtro="{e(t)}" aria-pressed="false">'
                        f'{e(TIPOS.get(t, t.capitalize()))}</button>')

        n = len(imoveis)
        corpo.append(f"""<section class="secao secao--clara">
  <div class="env">
    <div class="lista-imoveis__barra">
      <div class="filtros" role="group" aria-label="Filtrar por tipo">{filtros}</div>
      <div class="campo campo--ordenar">
        <label for="ordenar-imoveis">Ordenar por</label>
        <select id="ordenar-imoveis">
          <option value="recentes">Mais recentes</option>
          <option value="preco-desc">Maior preço</option>
          <option value="preco-asc">Menor preço</option>
          <option value="area-desc">Maior área</option>
          <option value="area-asc">Menor área</option>
        </select>
      </div>
    </div>
    <p style="color:var(--tinta-suave);font-size:.9rem;margin-bottom:1.75rem">
      <span id="contador-imoveis">{n} {'propriedade' if n == 1 else 'propriedades'}</span>
    </p>
    <div class="grade-imoveis" id="grade-imoveis">{''.join(card_imovel(i, cambio=cfg.get('cambio')) for i in imoveis)}</div>
  </div>
</section>""")
    else:
        corpo.append(f"""<section class="secao">
  <div class="env">
    <div class="vazio">
      <h2>{e(s.get('vazio_titulo', 'Portfólio em atualização'))}</h2>
      <p>{e(s.get('vazio_texto', ''))}</p>
      <div class="grupo-btn" style="justify-content:center;margin-top:2rem">
        <a class="btn btn--principal" href="/contato/">Falar com um especialista</a>
      </div>
    </div>
  </div>
</section>""")

    corpo.append(cta_faixa(cfg, "Procura algo específico?",
                           "Diga região, tamanho, aptidão e faixa de investimento. Boa parte do que negociamos não chega a ser anunciado."))

    dominio = cfg["site"]["dominio"].rstrip("/")
    ld = json.dumps({
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": s.get("titulo", "Imóveis rurais à venda"),
        "description": s.get("chamada", ""),
        "url": dominio + "/imoveis/",
        "mainEntity": {
            "@type": "ItemList",
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "url": dominio + im["url"], "name": im["titulo"]}
                for i, im in enumerate(imoveis)
            ],
        },
    }, ensure_ascii=False)
    ld_migalha = ld_breadcrumbs(cfg, [("Início", "/"), ("Imóveis", "/imoveis/")])

    return pagina(cfg, titulo=s.get("titulo", "Imóveis rurais à venda"),
                  descricao=s.get("descricao_meta", s.get("chamada", "")), url="/imoveis/",
                  corpo="\n".join(corpo), json_ld=[ld, ld_migalha],
                  rascunho=any(i.get("_exemplo") or i.get("_rascunho") for i in imoveis),
                  hreflang=hreflang_para(cfg, "/imoveis/"))


def gerar_ficha_imovel(cfg, im, todos_imoveis) -> str:
    local = ", ".join(x for x in [im.get("municipio"), im.get("estado")] if x)
    olho = " · ".join(x for x in [local, TIPOS.get(im.get("tipo", ""), ""), im.get("regiao", "")] if x)

    # resumo-imovel: a faixa "poucas fotos, poucas informações, fale
    # conosco" — nome, região, área total, valor (ou "sob consulta") e uma
    # chamada forte de contato, tudo visível logo abaixo do título, sem
    # precisar rolar até o painel lateral. Ficha técnica item a item (o que
    # antes vivia aqui como "ficha rápida") virou uma seção discreta lá
    # embaixo — ver bloco "ficha-tecnica".
    resumo_dados = []
    if local:
        resumo_dados.append(f'<div class="dado"><span class="dado__rot">Região</span>'
                            f'<span class="dado__val">{e(local)}</span></div>')
    if im.get("area_total_ha"):
        resumo_dados.append(f'<div class="dado"><span class="dado__rot">Área total</span>'
                            f'<span class="dado__val">{fmt_num(im["area_total_ha"])} ha</span></div>')
    if im.get("preco_sob_consulta") or not im.get("preco"):
        resumo_dados.append('<div class="dado"><span class="dado__rot">Valor</span>'
                            '<span class="dado__val dado__val--preco">Sob consulta</span></div>')
    else:
        resumo_dados.append(f'<div class="dado"><span class="dado__rot">Valor</span>'
                            f'<span class="dado__val dado__val--preco">{e(fmt_reais(im["preco"]))}</span></div>')

    link_imovel = cfg["site"]["dominio"].rstrip("/") + im["url"]
    msg = f"Olá! Tenho interesse na {im['titulo']} ({local}). Vi no site da Prime Fazendas: {link_imovel}"
    zap = montar_url_zap(cfg, msg)
    if zap:
        acao_resumo = (f'<a class="btn btn--principal" href="{e(zap)}" target="_blank" rel="noopener">'
                       f'Falar com um especialista</a>')
    else:
        acao_resumo = '<a class="btn btn--principal" href="/contato/">Falar com um especialista</a>'

    resumo_imovel = (f'<div class="resumo-imovel">'
                     f'<div class="resumo-imovel__dados">{"".join(resumo_dados)}</div>'
                     f'<div class="resumo-imovel__acao">{acao_resumo}</div>'
                     f'</div>') if resumo_dados else ""

    corpo = [f'<section class="secao secao--compacta"><div class="env">'
             + migalhas([("Início", "/"), ("Imóveis", "/imoveis/"), (im["titulo"], "")])
             + f'<p class="olho">{e(olho)}</p><h1>{e(im["titulo"])}</h1>'
             + (f'<p class="chamada chamada--larga">{e(im["subtitulo"])}</p>' if im.get("subtitulo") else "")
             + resumo_imovel
             + "</div></section>"]

    # galeria — vem exclusivamente do conjunto curado manualmente (ver
    # carregar_imoveis). Poucas fotos, grandes, sem grade apertada.
    blocos = []
    if im["fotos_url"]:
        local_galeria = ", ".join(x for x in [im.get("municipio"), im.get("estado")] if x)
        fotos = "".join(
            f'<a class="galeria__link js-foto-modal" href="{e(u)}" '
            f'data-foto-modal-src="{e(u)}" '
            f'data-foto-modal-alt="{e(descricao_foto(u, im["titulo"], local_galeria))} — foto {n + 1}" '
            f'title="Abrir foto {n + 1} no visualizador">'
            f'<img src="{e(u)}" alt="{e(descricao_foto(u, im["titulo"], local_galeria))} — foto {n + 1}" '
            f'width="{(dim := dimensoes_midia_url(u, 1200, 900))[0]}" height="{dim[1]}" '
            f'loading="lazy" sizes="(max-width: 640px) 100vw, 50vw">'
            f'</a>'
            for n, u in enumerate(im["fotos_url"])
        )
        blocos.append(f'<div class="galeria galeria--curada">{fotos}</div>')
    if im.get("descricao"):
        blocos.append(f'<div class="bloco-ficha"><h3>A propriedade</h3>'
                      f'<div class="prosa">{paragrafos(im["descricao"])}</div></div>')

    # Ficha técnica completa: dados mais densos (características, infra item
    # a item, documentação, vídeo, mapa) ficam visualmente em segundo plano,
    # dentro de um <details> fechado por padrão — não competem com a galeria
    # e o CTA no topo da página, mas continuam a um clique de distância.
    detalhes = []

    for titulo, chave in [("Características", "caracteristicas"),
                          ("Infraestrutura", "infraestrutura"),
                          ("Documentação", "documentacao")]:
        itens = im.get(chave) or []
        if itens:
            marcador = "marcada marcada--check" if chave == "documentacao" else "marcada"
            detalhes.append(f'<div class="bloco-ficha"><h3>{e(titulo)}</h3>'
                            f'<ul class="{marcador}">'
                            + "".join(f"<li>{e(i)}</li>" for i in itens) + "</ul></div>")

    if preenchido(im.get("video_youtube")):
        vid = e(im["video_youtube"])
        detalhes.append(f'<div class="bloco-ficha"><h3>Vídeo</h3><div class="mapa">'
                        f'<iframe src="https://www.youtube-nocookie.com/embed/{vid}" '
                        f'title="Vídeo da propriedade" loading="lazy" allowfullscreen></iframe></div></div>')

    mapa_embed_url = im.get("mapa_embed") if preenchido(im.get("mapa_embed")) else ""
    mapa_titulo = "Localização"
    mapa_legenda = ""
    if not mapa_embed_url:
        municipio_estado = ", ".join(x for x in [im.get("municipio"), im.get("estado")] if preenchido(x))
        if municipio_estado:
            mapa_embed_url = f"https://www.google.com/maps?q={url_quote(municipio_estado)}&output=embed"
            mapa_legenda = (f'<p class="form__nota" style="margin-top:.6rem">Mapa aproximado do '
                            f'município — {e(municipio_estado)}. Não representa os limites exatos '
                            f'da propriedade.</p>')
    if mapa_embed_url:
        detalhes.append(f'<div class="bloco-ficha"><h3>{e(mapa_titulo)}</h3><div class="mapa">'
                        f'<iframe src="{e(mapa_embed_url)}" title="Mapa da propriedade" '
                        f'loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe></div>'
                        f'{mapa_legenda}</div>')

    # dado de área aberta/reserva entra na ficha técnica completa (não no
    # resumo do topo, que fica só com o essencial: região, área total, valor).
    areas_extra = []
    if im.get("area_aberta_ha"):
        areas_extra.append(f'<div class="dado"><span class="dado__rot">Área aberta</span>'
                           f'<span class="dado__val">{fmt_num(im["area_aberta_ha"])} ha</span></div>')
    if im.get("area_reserva_ha"):
        areas_extra.append(f'<div class="dado"><span class="dado__rot">Reserva / APP</span>'
                           f'<span class="dado__val">{fmt_num(im["area_reserva_ha"])} ha</span></div>')
    rotulo_status_rapido, _ = STATUS.get(im.get("status", "disponivel"), STATUS["disponivel"])
    areas_extra.append(f'<div class="dado"><span class="dado__rot">Situação</span>'
                       f'<span class="dado__val">{e(rotulo_status_rapido)}</span></div>')
    if areas_extra:
        detalhes.insert(0, f'<div class="bloco-ficha"><h3>Números da propriedade</h3>'
                        f'<div class="imovel__dados imovel__dados--ficha">{"".join(areas_extra)}</div></div>')

    if detalhes:
        blocos.append('<details class="ficha-tecnica"><summary class="ficha-tecnica__abrir">'
                      'Ficha técnica completa</summary>'
                      f'<div class="ficha-tecnica__corpo">{"".join(detalhes)}</div></details>')

    # painel lateral
    cambio = cfg.get("cambio")
    if im.get("preco_sob_consulta") or not im.get("preco"):
        preco_html = '<p class="painel__preco">Sob consulta</p>'
        nota = '<p class="painel__preco-nota">Valor informado no primeiro contato.</p>'
    else:
        preco_html = f'<p class="painel__preco">{e(fmt_reais(im["preco"]))}{preco_usd_html(im["preco"], cambio, "painel__preco-usd")}</p>'
        nota = ""
        if im.get("preco_ha"):
            nota = (f'<p class="painel__preco-nota">≈ R$ {fmt_num(round(im["preco_ha"]))} por hectare</p>')
        nota += nota_cambio_html(cambio, "pt")
    nota += '<p class="painel__alerta">Preço, área e disponibilidade são confirmados antes de qualquer proposta.</p>'

    linhas = []
    if im.get("area_total_ha"):
        linhas.append(("Área total", f'{fmt_num(im["area_total_ha"])} ha'))
    if im.get("area_aberta_ha"):
        linhas.append(("Área aberta", f'{fmt_num(im["area_aberta_ha"])} ha'))
    if im.get("area_reserva_ha"):
        linhas.append(("Reserva / APP", f'{fmt_num(im["area_reserva_ha"])} ha'))
    if local:
        linhas.append(("Localização", local))
    if im.get("regiao"):
        linhas.append(("Região", im["regiao"]))
    if im.get("tipo"):
        linhas.append(("Aptidão", TIPOS.get(im["tipo"], im["tipo"])))
    rotulo_status, _ = STATUS.get(im.get("status", "disponivel"), STATUS["disponivel"])
    linhas.append(("Situação", rotulo_status))

    linhas_html = "".join(
        f'<li><span class="rot">{e(r)}</span><span class="val">{e(v)}</span></li>'
        for r, v in linhas
    )

    link_imovel = cfg["site"]["dominio"].rstrip("/") + im["url"]
    msg = f"Olá! Tenho interesse na {im['titulo']} ({local}). Vi no site da Prime Fazendas: {link_imovel}"
    zap = montar_url_zap(cfg, msg)
    acoes = f'<a class="btn btn--principal btn--bloco" href="/contato/">Agendar visita</a>'
    if zap:
        acoes = (f'<a class="btn btn--principal btn--bloco" href="{e(zap)}" target="_blank" '
                 f'rel="noopener">Falar sobre esta propriedade</a>'
                 f'<a class="btn btn--vazado btn--bloco" href="/contato/" style="margin-top:.7rem">Agendar visita</a>')

    painel = f"""<aside class="painel">
  {preco_html}{nota}
  <ul class="painel__linhas">{linhas_html}</ul>
  {acoes}
  <p class="form__nota" style="margin-top:1.1rem">Dados sujeitos a confirmação em due diligence.</p>
  <p class="form__nota">Ficha atualizada em {e(fmt_data(date.today()))}.</p>
</aside>"""

    corpo.append(f'<section class="secao secao--compacta"><div class="env">'
                 f'<div class="ficha"><div>{"".join(blocos)}</div>{painel}</div></div></section>')

    # imóveis relacionados — linkagem interna para outras fazendas da mesma
    # UF ou de área parecida, reaproveitando o mesmo card da listagem (sem
    # criar um componente visual novo, para não fugir do padrão minimalista).
    relacionados = imoveis_relacionados(im, todos_imoveis)
    if relacionados:
        corpo.append(f"""<section class="secao secao--clara">
  <div class="env">
    <div class="cabeca-secao">
      <p class="olho">Também pode interessar</p>
      <h2>Imóveis relacionados</h2>
    </div>
    <div class="grade-imoveis">{''.join(card_imovel(o, cambio=cfg.get('cambio')) for o in relacionados)}</div>
  </div>
</section>""")

    corpo.append(cta_faixa(cfg, "Quer ver outras opções?",
                           "Temos propriedades que não estão publicadas no site.",
                           "Falar com um especialista"))

    desc = descricao_meta_imovel(im)
    ld = json.dumps({
        "@context": "https://schema.org",
        "@type": "RealEstateListing",
        "name": im["titulo"],
        "description": desc,
        "url": cfg["site"]["dominio"].rstrip("/") + im["url"],
        "address": {
            "@type": "PostalAddress",
            "addressLocality": im.get("municipio", ""),
            "addressRegion": im.get("estado", ""),
            "addressCountry": "BR",
        },
        **({"image": [
            {"@type": "ImageObject",
             "contentUrl": cfg["site"]["dominio"].rstrip("/") + u,
             "width": dimensoes_midia_url(u, 1200, 900)[0],
             "height": dimensoes_midia_url(u, 1200, 900)[1]}
            for u in im["fotos_url"]
        ]} if im["fotos_url"] else {}),
        **({"floorSize": {
            "@type": "QuantitativeValue",
            "value": im["area_total_ha"],
            "unitText": "ha",
        }} if im.get("area_total_ha") else {}),
        **({"offers": {
            "@type": "Offer",
            "price": im["preco"],
            "priceCurrency": "BRL",
            "availability": ("https://schema.org/InStock"
                             if im.get("status") == "disponivel"
                             else "https://schema.org/OutOfStock"),
        }} if im.get("preco") and not im.get("preco_sob_consulta") else {}),
    }, ensure_ascii=False)
    ld_migalha = ld_breadcrumbs(cfg, [("Início", "/"), ("Imóveis", "/imoveis/"), (im["titulo"], im["url"])])

    og_img_imovel = (cfg["site"]["dominio"].rstrip("/") + im["fotos_url"][0]) if im.get("fotos_url") else ""

    return pagina(cfg, titulo=im["titulo"], descricao=desc, url=im["url"],
                  corpo="\n".join(corpo), og_tipo="article", json_ld=[ld, ld_migalha],
                  rascunho=bool(im.get("_exemplo") or im.get("_rascunho")),
                  og_imagem=og_img_imovel, hreflang=hreflang_para(cfg, im["url"]))


TIPOS_I18N = {
    "en": {"agricola": "Cropland", "pecuaria": "Cattle ranching", "mista": "Mixed use",
           "reflorestamento": "Reforestation", "lazer": "Leisure"},
    "zh": {"agricola": "农业用地", "pecuaria": "畜牧业", "mista": "农牧混合",
           "reflorestamento": "植树造林", "lazer": "休闲用地"},
}

STATUS_I18N = {
    "en": {"disponivel": ("Available", "selo--azul"), "reservado": ("Reserved", "selo--dourado"),
           "vendido": ("Sold", "selo--vendido")},
    "zh": {"disponivel": ("可售", "selo--azul"), "reservado": ("已预订", "selo--dourado"),
           "vendido": ("已售出", "selo--vendido")},
}

TEXTOS_IMOVEL_I18N = {
    "en": {
        "area_total": "Total area", "valor": "Price", "sob_consulta": "Available on request",
        "regiao": "Region", "localizacao": "Location", "aptidao": "Suitability", "situacao": "Status",
        "area_aberta": "Cleared area", "reserva": "Reserve / APP", "documentos_verificados": "Documents verified",
        "rascunho": "Draft — not published", "exemplo": "Example",
        "falar_especialista": "Talk to a specialist", "agendar_visita": "Schedule a visit",
        "falar_sobre": "Ask about this property", "propriedade": "property", "propriedades": "properties",
        "inicio": "Home", "imoveis_nav": "Properties", "a_propriedade": "The property",
        "caracteristicas": "Features", "infraestrutura": "Infrastructure", "documentacao": "Documentation",
        "video": "Video", "localizacao_titulo": "Location", "numeros": "Property numbers",
        "ficha_completa": "Full property sheet", "tambem_interessar": "You may also be interested",
        "imoveis_relacionados": "Related properties", "quer_ver_outras": "Want to see other options?",
        "temos_nao_publicadas": "We have properties that are not published on the site.",
        "preco_confirmado": "Price, area and availability are confirmed before any proposal.",
        "por_hectare": "per hectare", "portfolio": "Portfolio", "imoveis_titulo": "Rural properties for sale",
        "todas": "All", "ordenar_por": "Sort by", "mais_recentes": "Most recent",
        "maior_preco": "Highest price", "menor_preco": "Lowest price", "maior_area": "Largest area",
        "menor_area": "Smallest area", "atualizado_em": "Sheet updated on",
        "sujeito_confirmacao": "Data subject to confirmation during due diligence.",
        "mapa_aviso": "Approximate map of the municipality — {local}. Does not represent the exact boundaries of the property.",
        "aviso_confirmado": ("Prices, area and availability are confirmed before publication. If a property "
                              "is reserved or under negotiation, it does not appear as available."),
        "portfolio_vazio_titulo": "Portfolio being updated", "diga_regiao": "Procura algo específico?",
    },
    "zh": {
        "area_total": "总面积", "valor": "价格", "sob_consulta": "价格面议",
        "regiao": "地区", "localizacao": "位置", "aptidao": "用途", "situacao": "状态",
        "area_aberta": "已开垦面积", "reserva": "保留地/APP", "documentos_verificados": "文件已核实",
        "rascunho": "草稿 — 未发布", "exemplo": "示例",
        "falar_especialista": "联系专业顾问", "agendar_visita": "预约看地",
        "falar_sobre": "咨询此房产", "propriedade": "处房产", "propriedades": "处房产",
        "inicio": "首页", "imoveis_nav": "房产项目", "a_propriedade": "房产介绍",
        "caracteristicas": "特点", "infraestrutura": "基础设施", "documentacao": "文件资料",
        "video": "视频", "localizacao_titulo": "位置", "numeros": "房产数据",
        "ficha_completa": "完整资料表", "tambem_interessar": "您可能还感兴趣",
        "imoveis_relacionados": "相关房产", "quer_ver_outras": "想看看其他选择吗？",
        "temos_nao_publicadas": "我们还有一些未在网站上公开的房产。",
        "preco_confirmado": "价格、面积及可售状态均在任何报价前予以确认。",
        "por_hectare": "每公顷", "portfolio": "项目组合", "imoveis_titulo": "在售乡村地产",
        "todas": "全部", "ordenar_por": "排序方式", "mais_recentes": "最新",
        "maior_preco": "价格从高到低", "menor_preco": "价格从低到高", "maior_area": "面积从大到小",
        "menor_area": "面积从小到大", "atualizado_em": "资料更新于",
        "sujeito_confirmacao": "数据须在尽职调查中予以确认。",
        "mapa_aviso": "该市镇的大致地图 — {local}。并不代表房产的确切边界。",
        "aviso_confirmado": "价格、面积及可售状态均在发布前予以确认。若某处房产处于预订或洽谈中，将不会显示为可售。",
        "portfolio_vazio_titulo": "项目组合更新中", "diga_regiao": "有具体需求？",
    },
}


def traduzir_imovel(im: dict, lang: str, trad_map: dict) -> dict:
    """Retorna uma copia do imovel com titulo/subtitulo/descricao/listas traduzidas
    (quando existir entrada em conteudo/imoveis_i18n.json) e url apontando para a
    versao no idioma. Fotos, preco, area e demais dados numericos sao os mesmos."""
    novo = dict(im)
    t = trad_map.get(im["slug"], {}).get(lang)
    if t:
        for campo in ("titulo", "subtitulo", "descricao", "caracteristicas", "infraestrutura", "documentacao"):
            if campo in t:
                novo[campo] = t[campo]
    # Sem traducao para este slug: mantem o link apontando para a ficha em
    # portugues (existente) em vez de um caminho /{lang}/... que nao foi gerado.
    novo["url"] = f"/{lang}/imoveis/{im['slug']}/" if t else im["url"]
    return novo


def card_imovel_i18n(im: dict, lang: str, cambio: dict | None = None) -> str:
    tx = TEXTOS_IMOVEL_I18N[lang]
    selos = []
    rotulo, classe = STATUS_I18N[lang].get(im.get("status", "disponivel"), STATUS_I18N[lang]["disponivel"])
    if im.get("status") != "disponivel":
        selos.append(f'<span class="selo {classe}">{e(rotulo)}</span>')
    if im.get("certificacao_ambiental"):
        selos.append(f'<span class="selo">{e(tx["documentos_verificados"])}</span>')
    if im.get("_rascunho"):
        selos.append(f'<span class="selo selo--aviso">{e(tx["rascunho"])}</span>')
    if im.get("_exemplo"):
        selos.append(f'<span class="selo selo--aviso">{e(tx["exemplo"])}</span>')

    local = ", ".join(x for x in [im.get("municipio"), im.get("estado")] if x)
    alt_capa = descricao_foto(im["fotos_url"][0], im["titulo"], local) if im["fotos_url"] else (
        f'{im["titulo"]} — {local}' if local else im["titulo"])

    if im["fotos_url"]:
        largura_capa, altura_capa = dimensoes_midia_url(im["fotos_url"][0], 1200, 750)
        capa = (f'<a class="imovel__capa-link js-foto-modal" href="{e(im["fotos_url"][0])}" '
                f'data-foto-modal-src="{e(im["fotos_url"][0])}" '
                f'data-foto-modal-alt="{e(alt_capa)}">'
                f'<img src="{e(im["fotos_url"][0])}" alt="{e(alt_capa)}" '
                f'width="{largura_capa}" height="{altura_capa}" loading="lazy" sizes="(max-width: 640px) 100vw, 50vw">'
                f'</a>')
    else:
        capa = SVG_CAPA

    tipo = TIPOS_I18N[lang].get(im.get("tipo", ""), "")
    cabeca = " · ".join(x for x in [local, tipo] if x)

    dados = []
    if im.get("area_total_ha"):
        dados.append(f'<div class="dado"><span class="dado__rot">{e(tx["area_total"])}</span>'
                     f'<span class="dado__val">{fmt_num(im["area_total_ha"])} ha</span></div>')
    if im.get("preco_sob_consulta") or not im.get("preco"):
        dados.append(f'<div class="dado"><span class="dado__rot">{e(tx["valor"])}</span>'
                     f'<span class="dado__val dado__val--preco">{e(tx["sob_consulta"])}</span></div>')
    else:
        dados.append(f'<div class="dado"><span class="dado__rot">{e(tx["valor"])}</span>'
                     f'<span class="dado__val dado__val--preco">{e(fmt_reais(im["preco"]))}'
                     f'{preco_usd_html(im["preco"], cambio)}</span></div>')
    preco_ordenacao = im["preco"] if im.get("preco") and not im.get("preco_sob_consulta") else 0
    area_ordenacao = im.get("area_total_ha") or 0

    return f"""<article class="imovel reveal" data-tipo="{e(im.get('tipo', ''))}" data-preco="{preco_ordenacao}" data-area="{area_ordenacao}">
  <div class="imovel__capa">
    {f'<div class="imovel__selos">{"".join(selos)}</div>' if selos else ''}
    {capa}
  </div>
  <div class="imovel__corpo">
    <p class="imovel__local">{e(cabeca)}</p>
    <h3 class="imovel__titulo"><a href="{e(im['url'])}">{e(im['titulo'])}</a></h3>
    <div class="imovel__dados">{''.join(dados)}</div>
  </div>
</article>"""


def gerar_lista_imoveis_i18n(cfg: dict, imoveis: list[dict], lang: str, trad_map: dict) -> str:
    tx = TEXTOS_IMOVEL_I18N[lang]
    imoveis_i18n = [traduzir_imovel(im, lang, trad_map) for im in imoveis]

    corpo = []
    corpo.append(f"""<section class="secao secao--compacta">
  <div class="env">
    <div class="painel__alerta" style="margin:0">{e(tx['aviso_confirmado'])}</div>
  </div>
</section>""")

    if imoveis_i18n:
        tipos_presentes = []
        for i in imoveis_i18n:
            if i.get("tipo") and i["tipo"] not in tipos_presentes:
                tipos_presentes.append(i["tipo"])

        filtros = f'<button class="filtro" data-filtro="todos" aria-pressed="true">{e(tx["todas"])}</button>'
        for t in tipos_presentes:
            filtros += (f'<button class="filtro" data-filtro="{e(t)}" aria-pressed="false">'
                        f'{e(TIPOS_I18N[lang].get(t, t.capitalize()))}</button>')

        n = len(imoveis_i18n)
        rotulo_n = tx["propriedade"] if n == 1 else tx["propriedades"]
        corpo.append(f"""<section class="secao secao--clara">
  <div class="env">
    <div class="lista-imoveis__barra">
      <div class="filtros" role="group" aria-label="Filtrar por tipo">{filtros}</div>
      <div class="campo campo--ordenar">
        <label for="ordenar-imoveis">{e(tx['ordenar_por'])}</label>
        <select id="ordenar-imoveis">
          <option value="recentes">{e(tx['mais_recentes'])}</option>
          <option value="preco-desc">{e(tx['maior_preco'])}</option>
          <option value="preco-asc">{e(tx['menor_preco'])}</option>
          <option value="area-desc">{e(tx['maior_area'])}</option>
          <option value="area-asc">{e(tx['menor_area'])}</option>
        </select>
      </div>
    </div>
    <p style="color:var(--tinta-suave);font-size:.9rem;margin-bottom:1.75rem">
      <span id="contador-imoveis">{n} {e(rotulo_n)}</span>
    </p>
    <div class="grade-imoveis" id="grade-imoveis">{''.join(card_imovel_i18n(i, lang, cambio=cfg.get('cambio')) for i in imoveis_i18n)}</div>
  </div>
</section>""")
    else:
        corpo.append(f"""<section class="secao">
  <div class="env">
    <div class="vazio">
      <h2>{e(tx['portfolio_vazio_titulo'])}</h2>
      <div class="grupo-btn" style="justify-content:center;margin-top:2rem">
        <a class="btn btn--principal" href="/{lang}/contato/">{e(tx['falar_especialista'])}</a>
      </div>
    </div>
  </div>
</section>""")

    corpo.append(cta_faixa_i18n(cfg, tx["diga_regiao"],
                                 "Tell us the region, size, suitability and investment range."
                                 if lang == "en" else "告诉我们地区、面积、用途及投资范围。",
                                 tx["falar_especialista"], lang))

    dominio = cfg["site"]["dominio"].rstrip("/")
    ld = json.dumps({
        "@context": "https://schema.org", "@type": "CollectionPage",
        "name": tx["imoveis_titulo"], "inLanguage": {"en": "en", "zh": "zh-Hans"}[lang],
        "url": dominio + f"/{lang}/imoveis/",
        "mainEntity": {
            "@type": "ItemList",
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "url": dominio + im["url"], "name": im["titulo"]}
                for i, im in enumerate(imoveis_i18n)
            ],
        },
    }, ensure_ascii=False)

    titulo = tx["imoveis_titulo"] + " | Prime Fazendas"
    ld_migalha = ld_breadcrumbs_i18n(cfg, lang, [({"en": "Properties", "zh": "房产项目"}[lang], f"/{lang}/imoveis/")])
    return _skeleton_i18n(cfg, lang, "/imoveis/", tx["imoveis_titulo"], tx["imoveis_titulo"],
                           "\n".join(corpo), [ld, ld_migalha])


def gerar_ficha_imovel_i18n(cfg: dict, im_pt: dict, todos_pt: list[dict], lang: str, trad_map: dict) -> str:
    tx = TEXTOS_IMOVEL_I18N[lang]
    im = traduzir_imovel(im_pt, lang, trad_map)
    local = ", ".join(x for x in [im.get("municipio"), im.get("estado")] if x)
    olho = " · ".join(x for x in [local, TIPOS_I18N[lang].get(im.get("tipo", ""), ""), im.get("regiao", "")] if x)

    resumo_dados = []
    if local:
        resumo_dados.append(f'<div class="dado"><span class="dado__rot">{e(tx["regiao"])}</span>'
                            f'<span class="dado__val">{e(local)}</span></div>')
    if im.get("area_total_ha"):
        resumo_dados.append(f'<div class="dado"><span class="dado__rot">{e(tx["area_total"])}</span>'
                            f'<span class="dado__val">{fmt_num(im["area_total_ha"])} ha</span></div>')
    if im.get("preco_sob_consulta") or not im.get("preco"):
        resumo_dados.append(f'<div class="dado"><span class="dado__rot">{e(tx["valor"])}</span>'
                            f'<span class="dado__val dado__val--preco">{e(tx["sob_consulta"])}</span></div>')
    else:
        resumo_dados.append(f'<div class="dado"><span class="dado__rot">{e(tx["valor"])}</span>'
                            f'<span class="dado__val dado__val--preco">{e(fmt_reais(im["preco"]))}</span></div>')

    acao_resumo = f'<a class="btn btn--principal" href="/{lang}/contato/">{e(tx["falar_especialista"])}</a>'

    resumo_imovel = (f'<div class="resumo-imovel">'
                     f'<div class="resumo-imovel__dados">{"".join(resumo_dados)}</div>'
                     f'<div class="resumo-imovel__acao">{acao_resumo}</div>'
                     f'</div>') if resumo_dados else ""

    migalha_html = ('<nav class="migalhas" aria-label="Breadcrumb"><ol>'
                    f'<li><a href="/{lang}/">{e(tx["inicio"])}</a></li>'
                    f'<li><a href="/{lang}/imoveis/">{e(tx["imoveis_nav"])}</a></li>'
                    f'<li aria-current="page">{e(im["titulo"])}</li></ol></nav>')

    corpo = [f'<section class="secao secao--compacta"><div class="env">'
             + migalha_html
             + f'<p class="olho">{e(olho)}</p><h1>{e(im["titulo"])}</h1>'
             + (f'<p class="chamada chamada--larga">{e(im["subtitulo"])}</p>' if im.get("subtitulo") else "")
             + resumo_imovel
             + "</div></section>"]

    blocos = []
    if im["fotos_url"]:
        local_galeria = ", ".join(x for x in [im.get("municipio"), im.get("estado")] if x)
        fotos = "".join(
            f'<a class="galeria__link js-foto-modal" href="{e(u)}" '
            f'data-foto-modal-src="{e(u)}" '
            f'data-foto-modal-alt="{e(descricao_foto(u, im["titulo"], local_galeria))} — {n + 1}" '
            f'>'
            f'<img src="{e(u)}" alt="{e(descricao_foto(u, im["titulo"], local_galeria))} — {n + 1}" '
            f'width="{(dim := dimensoes_midia_url(u, 1200, 900))[0]}" height="{dim[1]}" '
            f'loading="lazy" sizes="(max-width: 640px) 100vw, 50vw">'
            f'</a>'
            for n, u in enumerate(im["fotos_url"])
        )
        blocos.append(f'<div class="galeria galeria--curada">{fotos}</div>')
    if im.get("descricao"):
        blocos.append(f'<div class="bloco-ficha"><h3>{e(tx["a_propriedade"])}</h3>'
                      f'<div class="prosa">{paragrafos(im["descricao"])}</div></div>')

    detalhes = []
    for titulo_bloco, chave in [(tx["caracteristicas"], "caracteristicas"),
                                (tx["infraestrutura"], "infraestrutura"),
                                (tx["documentacao"], "documentacao")]:
        itens = im.get(chave) or []
        if itens:
            marcador = "marcada marcada--check" if chave == "documentacao" else "marcada"
            detalhes.append(f'<div class="bloco-ficha"><h3>{e(titulo_bloco)}</h3>'
                            f'<ul class="{marcador}">' + "".join(f"<li>{e(i)}</li>" for i in itens) + "</ul></div>")

    if preenchido(im.get("video_youtube")):
        vid = e(im["video_youtube"])
        detalhes.append(f'<div class="bloco-ficha"><h3>{e(tx["video"])}</h3><div class="mapa">'
                        f'<iframe src="https://www.youtube-nocookie.com/embed/{vid}" '
                        f'title="{e(tx["video"])}" loading="lazy" allowfullscreen></iframe></div></div>')

    mapa_embed_url = im.get("mapa_embed") if preenchido(im.get("mapa_embed")) else ""
    mapa_legenda = ""
    if not mapa_embed_url:
        municipio_estado = ", ".join(x for x in [im.get("municipio"), im.get("estado")] if preenchido(x))
        if municipio_estado:
            mapa_embed_url = f"https://www.google.com/maps?q={url_quote(municipio_estado)}&output=embed"
            mapa_legenda = (f'<p class="form__nota" style="margin-top:.6rem">'
                            f'{e(tx["mapa_aviso"].format(local=municipio_estado))}</p>')
    if mapa_embed_url:
        detalhes.append(f'<div class="bloco-ficha"><h3>{e(tx["localizacao_titulo"])}</h3><div class="mapa">'
                        f'<iframe src="{e(mapa_embed_url)}" title="{e(tx["localizacao_titulo"])}" '
                        f'loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe></div>'
                        f'{mapa_legenda}</div>')

    areas_extra = []
    if im.get("area_aberta_ha"):
        areas_extra.append(f'<div class="dado"><span class="dado__rot">{e(tx["area_aberta"])}</span>'
                           f'<span class="dado__val">{fmt_num(im["area_aberta_ha"])} ha</span></div>')
    if im.get("area_reserva_ha"):
        areas_extra.append(f'<div class="dado"><span class="dado__rot">{e(tx["reserva"])}</span>'
                           f'<span class="dado__val">{fmt_num(im["area_reserva_ha"])} ha</span></div>')
    rotulo_status_rapido, _ = STATUS_I18N[lang].get(im.get("status", "disponivel"), STATUS_I18N[lang]["disponivel"])
    areas_extra.append(f'<div class="dado"><span class="dado__rot">{e(tx["situacao"])}</span>'
                       f'<span class="dado__val">{e(rotulo_status_rapido)}</span></div>')
    if areas_extra:
        detalhes.insert(0, f'<div class="bloco-ficha"><h3>{e(tx["numeros"])}</h3>'
                        f'<div class="imovel__dados imovel__dados--ficha">{"".join(areas_extra)}</div></div>')

    if detalhes:
        blocos.append(f'<details class="ficha-tecnica"><summary class="ficha-tecnica__abrir">'
                      f'{e(tx["ficha_completa"])}</summary>'
                      f'<div class="ficha-tecnica__corpo">{"".join(detalhes)}</div></details>')

    cambio = cfg.get("cambio")
    if im.get("preco_sob_consulta") or not im.get("preco"):
        preco_html = f'<p class="painel__preco">{e(tx["sob_consulta"])}</p>'
        nota = ""
    else:
        preco_html = f'<p class="painel__preco">{e(fmt_reais(im["preco"]))}{preco_usd_html(im["preco"], cambio, "painel__preco-usd")}</p>'
        nota = ""
        if im.get("preco_ha"):
            nota = f'<p class="painel__preco-nota">≈ R$ {fmt_num(round(im["preco_ha"]))} {e(tx["por_hectare"])}</p>'
        nota += nota_cambio_html(cambio, lang)
    nota += f'<p class="painel__alerta">{e(tx["preco_confirmado"])}</p>'

    linhas = []
    if im.get("area_total_ha"):
        linhas.append((tx["area_total"], f'{fmt_num(im["area_total_ha"])} ha'))
    if im.get("area_aberta_ha"):
        linhas.append((tx["area_aberta"], f'{fmt_num(im["area_aberta_ha"])} ha'))
    if im.get("area_reserva_ha"):
        linhas.append((tx["reserva"], f'{fmt_num(im["area_reserva_ha"])} ha'))
    if local:
        linhas.append((tx["localizacao"], local))
    if im.get("regiao"):
        linhas.append((tx["regiao"], im["regiao"]))
    if im.get("tipo"):
        linhas.append((tx["aptidao"], TIPOS_I18N[lang].get(im["tipo"], im["tipo"])))
    rotulo_status, _ = STATUS_I18N[lang].get(im.get("status", "disponivel"), STATUS_I18N[lang]["disponivel"])
    linhas.append((tx["situacao"], rotulo_status))

    linhas_html = "".join(
        f'<li><span class="rot">{e(r)}</span><span class="val">{e(v)}</span></li>' for r, v in linhas
    )

    acoes = (f'<a class="btn btn--principal btn--bloco" href="/{lang}/contato/">{e(tx["falar_sobre"])}</a>')

    painel = f"""<aside class="painel">
  {preco_html}{nota}
  <ul class="painel__linhas">{linhas_html}</ul>
  {acoes}
  <p class="form__nota" style="margin-top:1.1rem">{e(tx["sujeito_confirmacao"])}</p>
  <p class="form__nota">{e(tx["atualizado_em"])} {e(fmt_data(date.today()))}.</p>
</aside>"""

    corpo.append(f'<section class="secao secao--compacta"><div class="env">'
                 f'<div class="ficha"><div>{"".join(blocos)}</div>{painel}</div></div></section>')

    relacionados_pt = imoveis_relacionados(im_pt, todos_pt)
    if relacionados_pt:
        relacionados_i18n = [traduzir_imovel(o, lang, trad_map) for o in relacionados_pt]
        corpo.append(f"""<section class="secao secao--clara">
  <div class="env">
    <div class="cabeca-secao"><p class="olho">{e(tx['tambem_interessar'])}</p><h2>{e(tx['imoveis_relacionados'])}</h2></div>
    <div class="grade-imoveis">{''.join(card_imovel_i18n(o, lang, cambio=cfg.get('cambio')) for o in relacionados_i18n)}</div>
  </div>
</section>""")

    corpo.append(cta_faixa_i18n(cfg, tx["quer_ver_outras"], tx["temos_nao_publicadas"], tx["falar_especialista"], lang))

    desc = im.get("subtitulo") or im.get("descricao", "")[:160] or im["titulo"]
    ld = json.dumps({
        "@context": "https://schema.org", "@type": "RealEstateListing", "inLanguage": {"en": "en", "zh": "zh-Hans"}[lang],
        "name": im["titulo"], "description": desc, "url": cfg["site"]["dominio"].rstrip("/") + im["url"],
        "address": {"@type": "PostalAddress", "addressLocality": im.get("municipio", ""),
                    "addressRegion": im.get("estado", ""), "addressCountry": "BR"},
        **({"image": [{"@type": "ImageObject", "contentUrl": cfg["site"]["dominio"].rstrip("/") + u,
                       "width": dimensoes_midia_url(u, 1200, 900)[0], "height": dimensoes_midia_url(u, 1200, 900)[1]}
                      for u in im["fotos_url"]]} if im.get("fotos_url") else {}),
        **({"floorSize": {"@type": "QuantitativeValue", "value": im["area_total_ha"], "unitText": "ha"}}
           if im.get("area_total_ha") else {}),
        **({"offers": {"@type": "Offer", "price": im["preco"], "priceCurrency": "BRL",
                       "availability": ("https://schema.org/InStock" if im.get("status") == "disponivel"
                                       else "https://schema.org/OutOfStock")}}
           if im.get("preco") and not im.get("preco_sob_consulta") else {}),
    }, ensure_ascii=False)

    ld_migalha = ld_breadcrumbs_i18n(cfg, lang, [
        ({"en": "Properties", "zh": "房产项目"}[lang], f"/{lang}/imoveis/"),
        (im["titulo"], im["url"]),
    ])
    return _skeleton_i18n(cfg, lang, im_pt["url"], im["titulo"], desc, "\n".join(corpo), [ld, ld_migalha])


CATEGORIA_I18N = {
    "en": {
        "Arrendamento": "Leasing", "Investimento": "Investment", "Tendências": "Trends",
        "Guia": "Guide", "Institucional": "Company", "Logística": "Logistics",
        "Jurídico": "Legal", "Mercado": "Market", "Exportação": "Exports",
        "Financiamento": "Financing", "Investidores internacionais": "International Investors",
        "Clima": "Climate", "Gestão": "Management", "Operação": "Operations",
        "Regularização": "Land Regularization", "Recursos Hídricos": "Water Resources",
        "Insights": "Insights", "Bem-estar": "Well-being", "Data Center": "Data Center",
    },
    "zh": {
        "Arrendamento": "土地租赁", "Investimento": "投资", "Tendências": "趋势",
        "Guia": "指南", "Institucional": "公司动态", "Logística": "物流",
        "Jurídico": "法律", "Mercado": "市场", "Exportação": "出口",
        "Financiamento": "融资", "Investidores internacionais": "国际投资者",
        "Clima": "气候", "Gestão": "管理", "Operação": "运营",
        "Regularização": "土地合规", "Recursos Hídricos": "水资源",
        "Insights": "洞察", "Bem-estar": "身心健康", "Data Center": "数据中心",
    },
}

TEXTOS_BLOG_I18N = {
    "en": {
        "noticias": "News", "noticias_insights": "News and insights", "mais_artigos": "More articles",
        "em_breve": "Coming soon", "continue_lendo": "Continue reading", "ler_artigo": "Read the article",
        "min_leitura": "min read", "portfolio_titulo": "Prime Fazendas Portfolio",
        "ja_leu": "Already read the news? Check out some available farms",
        "ver_todas": "See all properties", "tem_propriedade": "Have a property or a question?",
        "fale_quem_negocia": "Talk to people who negotiate land in Tocantins every day.",
        "acervo": "Illustrative image — Prime Fazendas archive",
    },
    "zh": {
        "noticias": "新闻资讯", "noticias_insights": "新闻与洞察", "mais_artigos": "更多文章",
        "em_breve": "敬请期待", "continue_lendo": "继续阅读", "ler_artigo": "阅读全文",
        "min_leitura": "分钟阅读", "portfolio_titulo": "Prime Fazendas 项目组合",
        "ja_leu": "看完新闻了吗？了解一些当前可售的农场",
        "ver_todas": "查看全部房产", "tem_propriedade": "有房产或疑问想咨询吗？",
        "fale_quem_negocia": "与每天在托坎廷斯州从事土地交易的专业团队沟通。",
        "acervo": "示意图片 — Prime Fazendas 资料库",
    },
}


def traduzir_post(p: dict, lang: str, trad_map: dict) -> dict:
    """Retorna uma copia do post com titulo/resumo/corpo traduzidos (quando existir
    entrada em conteudo/noticias_i18n.json) e url apontando para a versao no idioma.
    Categoria mantem o valor PT original em '_categoria_pt' (usado so pelo icone),
    e ganha o rotulo traduzido em 'categoria'."""
    novo = dict(p)
    t = trad_map.get(p["slug"], {}).get(lang)
    categoria_pt = p.get("categoria", "")
    if t:
        novo["titulo"] = t.get("titulo", novo["titulo"])
        novo["resumo"] = t.get("resumo", novo.get("resumo", ""))
        novo["html"] = markdown(t.get("corpo_markdown", ""))
    novo["_categoria_pt"] = categoria_pt
    novo["categoria"] = CATEGORIA_I18N[lang].get(categoria_pt, categoria_pt)
    # Sem traducao para este slug: mantem o link apontando para o post em
    # portugues (existente) em vez de um caminho /{lang}/... que nao foi gerado.
    novo["url"] = f"/{lang}/blog/{p['slug']}/" if t else p["url"]
    return novo


def card_post_i18n(p: dict, lang: str, destaque: bool = False) -> str:
    tx = TEXTOS_BLOG_I18N[lang]
    tempo = p.get('tempo_leitura')
    meta_tempo = f'<span>·</span><span>{tempo} {e(tx["min_leitura"])}</span>' if tempo else ''
    classe = "post-card post-card--destaque reveal" if destaque else "post-card reveal"
    icone_cat = p.get("_categoria_pt", p["categoria"])
    if preenchido(p.get('capa')):
        largura_post, altura_post = dimensoes_midia_url(p["capa"], 640, 400)
        capa = (f'<a class="post-card__capa post-card__capa--foto" href="{e(p["url"])}" '
                f'aria-hidden="true" tabindex="-1">'
                f'<img src="{e(p["capa"])}" alt="{e(p["titulo"])}" loading="lazy" '
                f'width="{largura_post}" height="{altura_post}">'
                f'<span class="post-card__selo">Prime News</span>'
                f'<span class="post-card__icone">{icone_noticia(icone_cat)}</span>'
                f'</a>')
    else:
        capa = (f'<a class="post-card__capa" href="{e(p["url"])}" aria-hidden="true" tabindex="-1">'
                f'<span class="post-card__selo">Prime News</span>'
                f'<span class="post-card__icone">{icone_noticia(icone_cat)}</span>'
                f'</a>')
    return f"""<article class="{classe}">
  {capa}
  <div class="post-card__corpo">
    <p class="post-card__meta"><span class="post-card__cat">{e(p['categoria'])}</span>
    <span>·</span><time datetime="{p['data'].isoformat()}">{e(fmt_data(p['data']))}</time>
    {meta_tempo}</p>
    <h3><a href="{e(p['url'])}">{e(p['titulo'])}</a></h3>
    {f"<p>{e(p['resumo'])}</p>" if p.get('resumo') else ''}
    <a class="link-seta" href="{e(p['url'])}">{e(tx['ler_artigo'])}</a>
  </div>
</article>"""


def gerar_blog_i18n(cfg: dict, posts: list[dict], imoveis: list[dict], lang: str, trad_map: dict,
                     imoveis_i18n_map: dict) -> str:
    tx = TEXTOS_BLOG_I18N[lang]
    posts_i18n = [traduzir_post(p, lang, trad_map) for p in posts]

    corpo = []
    if posts_i18n:
        destaque, resto = posts_i18n[0], posts_i18n[1:]
        corpo.append(f'<section class="secao secao--compacta"><div class="env">'
                     f'{card_post_i18n(destaque, lang, destaque=True)}'
                     f"</div></section>")
        if resto:
            corpo.append(f'<section class="secao secao--clara"><div class="env">'
                         f'<div class="cabeca-secao"><p class="olho">{e(tx["mais_artigos"])}</p></div>'
                         f'<div class="grade-posts">{"".join(card_post_i18n(p, lang) for p in resto)}</div>'
                         f"</div></section>")
    else:
        corpo.append(f'<section class="secao"><div class="env"><div class="vazio">'
                     f'<h2>{e(tx["em_breve"])}</h2></div></div></section>')

    destaques_imoveis_pt = [i for i in imoveis if i.get("destaque")] or imoveis[:3]
    if destaques_imoveis_pt:
        from_lang_imoveis = []
        for i in destaques_imoveis_pt[:3]:
            if i["slug"] in imoveis_i18n_map:
                from_lang_imoveis.append(traduzir_imovel(i, lang, imoveis_i18n_map))
            else:
                from_lang_imoveis.append(i)
        bloco_portfolio = ('<section class="secao secao--clara">'
                            '<div class="env">'
                            '<div class="cabeca-secao">'
                            f'<p class="olho">{e(tx["portfolio_titulo"])}</p>'
                            f'<h2>{e(tx["ja_leu"])}</h2>'
                            '</div>'
                            f'<div class="grade-imoveis">{"".join(card_imovel_i18n(i, lang, cambio=cfg.get("cambio")) for i in from_lang_imoveis)}</div>'
                            f'<p style="margin-top:2.5rem"><a class="link-seta" href="/{lang}/imoveis/">{e(tx["ver_todas"])}</a></p>'
                            '</div></section>')
        corpo.append(bloco_portfolio)

    dominio = cfg["site"]["dominio"].rstrip("/")
    ld = json.dumps({
        "@context": "https://schema.org", "@type": "CollectionPage", "inLanguage": {"en": "en", "zh": "zh-Hans"}[lang],
        "name": tx["noticias_insights"], "url": dominio + f"/{lang}/blog/",
    }, ensure_ascii=False)

    ld_migalha = ld_breadcrumbs_i18n(cfg, lang, [({"en": "News", "zh": "新闻资讯"}[lang], f"/{lang}/blog/")])
    return _skeleton_i18n(cfg, lang, "/blog/", tx["noticias_insights"], tx["noticias_insights"],
                           "\n".join(corpo), [ld, ld_migalha])


def gerar_post_i18n(cfg: dict, p_pt: dict, outros_pt: list[dict], lang: str, trad_map: dict) -> str:
    tx = TEXTOS_BLOG_I18N[lang]
    p = traduzir_post(p_pt, lang, trad_map)

    capa_html = ""
    if preenchido(p.get('capa')):
        capa_html = (
            '<section class="secao secao--compacta secao--sem-topo"><div class="env">'
            '<div class="artigo"><figure class="artigo__capa">'
            f'<img src="{e(p["capa"])}" alt="{e(p["titulo"])}" loading="lazy" width="1200" height="675">'
            f'<figcaption>{e(tx["acervo"])}</figcaption>'
            '</figure></div></div></section>'
        )

    migalha_home = "Home" if lang == "en" else "首页"
    migalha_html = ('<nav class="migalhas" aria-label="Breadcrumb"><ol>'
                    f'<li><a href="/{lang}/">{migalha_home}</a></li>'
                    f'<li><a href="/{lang}/blog/">{e(tx["noticias"])}</a></li>'
                    f'<li aria-current="page">{e(p["titulo"])}</li></ol></nav>')

    meta_tempo_post = ""
    if p.get("tempo_leitura"):
        meta_tempo_post = f'<span>\u00b7</span><span>{p["tempo_leitura"]} {e(tx["min_leitura"])}</span>'
    chamada_post = ""
    if p.get("resumo"):
        chamada_post = f'<p class="chamada chamada--larga">{e(p["resumo"])}</p>'

    corpo = [(f'<section class="secao secao--compacta">'
              f'<div class="env">'
              f'<div class="artigo">'
              f'{migalha_html}'
              f'<p class="artigo__meta"><span class="post-card__cat">{e(p["categoria"])}</span>'
              f'<span>\u00b7</span><time datetime="{p["data"].isoformat()}">{e(fmt_data(p["data"]))}</time>'
              f'<span>\u00b7</span><span>{e(p["autor"])}</span>'
              f'{meta_tempo_post}</p>'
              f'<h1>{e(p["titulo"])}</h1>'
              f'{chamada_post}'
              f'</div></div></section>'
              f'{capa_html}'
              f'<section class="secao secao--compacta"><div class="env">'
              f'<article class="artigo prosa artigo__corpo">{p["html"]}</article>'
              f'</div></section>')]

    relacionados_pt = [o for o in outros_pt if o["slug"] != p_pt["slug"]][:2]
    if relacionados_pt:
        relacionados_i18n = [traduzir_post(o, lang, trad_map) for o in relacionados_pt]
        bloco_relacionados = ('<section class="secao secao--clara"><div class="env">'
                              f'<div class="cabeca-secao"><p class="olho">{e(tx["continue_lendo"])}</p></div>'
                              f'<div class="grade-posts">{"".join(card_post_i18n(o, lang) for o in relacionados_i18n)}</div>'
                              '</div></section>')
        corpo.append(bloco_relacionados)

    corpo.append(cta_faixa_i18n(cfg, tx["tem_propriedade"], tx["fale_quem_negocia"], TEXTOS_IMOVEL_I18N[lang]["falar_especialista"], lang))

    dominio = cfg["site"]["dominio"].rstrip("/")
    ld = json.dumps({
        "@context": "https://schema.org", "@type": "Article", "inLanguage": {"en": "en", "zh": "zh-Hans"}[lang],
        "headline": p["titulo"], "description": p.get("resumo", ""),
        "datePublished": p["data"].isoformat(), "dateModified": p["data"].isoformat(),
        **({"image": dominio + p["capa"]} if preenchido(p.get("capa")) else {}),
        "author": {"@type": "Organization", "name": p["autor"]},
        "publisher": {"@type": "Organization", "name": cfg["marca"]["nome"]},
        "mainEntityOfPage": dominio + p["url"],
    }, ensure_ascii=False)

    ld_migalha = ld_breadcrumbs_i18n(cfg, lang, [
        ({"en": "News", "zh": "新闻资讯"}[lang], f"/{lang}/blog/"),
        (p["titulo"], p["url"]),
    ])
    return _skeleton_i18n(cfg, lang, p_pt["url"], p["titulo"], p.get("resumo", ""), "\n".join(corpo), [ld, ld_migalha])




def gerar_redirect(cfg, destino: str) -> str:
    """Pagina simples de redirecionamento (usada para URLs antigas que saem do menu,
    ex.: /comunidade/ apos a fusao do conteudo dentro do Blog)."""
    dominio = cfg["site"]["dominio"].rstrip("/")
    destino_absoluto = dominio + destino
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="0; url={e(destino_absoluto)}">
<link rel="canonical" href="{e(destino_absoluto)}">
<title>Redirecionando…</title>
</head>
<body>
<h1>Comunidade agora faz parte de Notícias</h1>
<p>Este conteúdo agora faz parte de <a href="{e(destino)}">Notícias</a>. Redirecionando…</p>
</body>
</html>
"""


def gerar_comunidade(cfg, pag) -> str:
    s = pag.get("comunidade", {})
    com = cfg.get("comunidade", {})

    grupo = com.get("grupo_whatsapp")
    canal = com.get("canal_whatsapp")
    botoes = ""
    if preenchido(grupo):
        botoes = (f'<a class="btn btn--dourado" href="{e(grupo)}" target="_blank" rel="noopener">'
                  f'Entrar no grupo do WhatsApp</a>')
    elif preenchido(canal):
        botoes = (f'<a class="btn btn--dourado" href="{e(canal)}" target="_blank" rel="noopener">'
                  f'Falar no WhatsApp</a>')
    else:
        botoes = '<a class="btn btn--dourado" href="/contato/">Quero entrar</a>'
        aviso("comunidade: 'grupo_whatsapp' e 'canal_whatsapp' estão vazios — o botão aponta para /contato/ até você colar um link válido.")

    corpo = [hero(cfg, olho="Comunidade", titulo=s.get("titulo", com.get("nome", "Comunidade")),
                  texto=s.get("chamada", ""), botoes=botoes, interno=True, foto="/midia/imoveis/fazenda-ametista-real/aerea-02.jpg")]

    corpo.append(f'<section class="secao"><div class="env"><div class="prosa">'
                 f'{paragrafos(s.get("intro"))}</div></div></section>')

    bens = "".join(
        f'<article class="card"><h3>{e(b["titulo"])}</h3><p>{e(b["texto"])}</p></article>'
        for b in s.get("beneficios", [])
    )
    if bens:
        corpo.append(f"""<section class="secao secao--clara">
  <div class="env">
    <div class="cabeca-secao"><p class="olho">O que você recebe</p>
    <h2>Por que participar</h2></div>
    <div class="grade grade--2">{bens}</div>
  </div>
</section>""")

    regras = "".join(f"<li>{e(r)}</li>" for r in s.get("regras", []))
    if regras:
        corpo.append(f"""<section class="secao">
  <div class="env"><div class="grade grade--2" style="align-items:start">
    <div><p class="olho">Combinado</p><h2>{e(s.get('regras_titulo', 'Como funciona'))}</h2></div>
    <ul class="marcada">{regras}</ul>
  </div></div>
</section>""")

    corpo.append(cta_faixa(cfg, s.get("cta_titulo", "Quero entrar na comunidade"),
                           s.get("cta_texto", ""), "Entrar em contato"))

    return pagina(cfg, titulo=s.get("titulo", "Comunidade"),
                  descricao=s.get("chamada", ""), url="/comunidade/", corpo="\n".join(corpo))


def gerar_blog(cfg, pag, posts, imoveis) -> str:
    s = pag.get("blog", {})
    corpo = [hero(cfg, olho="Notícias", titulo=s.get("titulo", "Notícias e insights"),
                  texto=s.get("chamada", ""), interno=True, foto="/midia/imoveis/fazenda-jade-do-campo/foto-01.jpg")]

    # comunidade absorvida pelo blog — deixou de ser item proprio do menu
    com = cfg.get("comunidade", {})
    canal = com.get("canal_whatsapp") or com.get("grupo_whatsapp")
    if preenchido(canal):
        corpo.append(f"""<section class="secao secao--compacta">
  <div class="env">
    <div class="cta-faixa">
      <h2>{e(com.get('nome', 'Comunidade Prime Agro'))}</h2>
      <p>{e(com.get('chamada', 'Receba os anúncios e novidades do agro direto no WhatsApp.'))}</p>
      <div class="grupo-btn"><a class="btn btn--dourado" href="{e(canal)}" target="_blank" rel="noopener">Entrar no grupo do WhatsApp</a></div>
    </div>
  </div>
</section>""")

    if posts:
        destaque, resto = posts[0], posts[1:]
        corpo.append(f'<section class="secao secao--compacta"><div class="env">'
                     f'{card_post(destaque, destaque=True)}'
                     f"</div></section>")
        if resto:
            corpo.append(f'<section class="secao secao--clara"><div class="env">'
                         f'<div class="cabeca-secao"><p class="olho">Mais artigos</p></div>'
                         f'<div class="grade-posts">{"".join(card_post(p) for p in resto)}</div>'
                         f"</div></section>")
    else:
        corpo.append(f'<section class="secao"><div class="env"><div class="vazio">'
                     f'<h2>{e(s.get("vazio_titulo", "Em breve"))}</h2>'
                     f'<p>{e(s.get("vazio_texto", ""))}</p></div></div></section>')

    # conecta com o portfólio de imóveis — só ao final, para não misturar notícia com anúncio
    destaques_imoveis = [i for i in imoveis if i.get("destaque")] or imoveis[:3]
    if destaques_imoveis:
        corpo.append(f'''<section class="secao secao--clara">
  <div class="env">
    <div class="cabeca-secao">
      <p class="olho">Portfólio Prime Fazendas</p>
      <h2>Já leu as notícias? Conheça algumas fazendas disponíveis</h2>
    </div>
    <div class="grade-imoveis">{"".join(card_imovel(i, cambio=cfg.get('cambio')) for i in destaques_imoveis[:3])}</div>
    <p style="margin-top:2.5rem"><a class="link-seta" href="/imoveis/">Ver todas as propriedades</a></p>
  </div>
</section>''')

    ld_migalha = ld_breadcrumbs(cfg, [("Início", "/"), ("Notícias", "/blog/")])

    return pagina(cfg, titulo=s.get("titulo", "Notícias"), descricao=s.get("chamada", ""),
                  url="/blog/", corpo="\n".join(corpo), json_ld=[ld_migalha],
                  hreflang=hreflang_para(cfg, "/blog/"))


def card_evento_agro(ev: dict, destaque: bool = False) -> str:
    local = ", ".join(x for x in [ev.get("cidade"), ev.get("estado")] if x)
    link = ""
    if preenchido(ev.get("url_oficial")):
        link = (f'<a class="link-seta" href="{e(ev["url_oficial"])}" target="_blank" '
                f'rel="noopener">Site oficial</a>')
    selo = '<span class="selo selo--dourado">Próximo evento</span>' if destaque else ''
    classe = "card card--evento-destaque" if destaque else "card"
    return f"""<article class="{classe}">
  {selo}
  <p class="olho">{e(fmt_intervalo(ev['data_inicio'], ev['data_fim']))}</p>
  <h3>{e(ev['nome'])}</h3>
  {f'<p>{e(local)}</p>' if local else ''}
  {f'<p>{e(ev["descricao"])}</p>' if ev.get('descricao') else ''}
  {link}
</article>"""


def agrupar_eventos_por_mes(agenda: list[dict]) -> list[tuple[str, list[dict]]]:
    """Agrupa eventos ja ordenados por data_inicio em blocos 'Mes de Ano',
    preservando a ordem cronologica (nao reordena, so agrupa em sequencia)."""
    grupos: list[tuple[str, list[dict]]] = []
    for ev in agenda:
        d = ev["data_inicio"]
        rotulo = f"{MESES[d.month - 1].capitalize()} de {d.year}"
        if grupos and grupos[-1][0] == rotulo:
            grupos[-1][1].append(ev)
        else:
            grupos.append((rotulo, [ev]))
    return grupos


def gerar_agenda_agro(cfg, pag, agenda) -> str:
    s = pag.get("agenda_agro", {})
    corpo = [hero(cfg, olho="Agenda Agro", titulo=s.get("titulo", "Agenda Agro"),
                  texto=s.get("chamada", ""), interno=True, foto="/midia/imoveis/fazenda-topazio-do-sol/foto-05.jpg")]

    if agenda:
        destaque, resto = agenda[0], agenda[1:]
        corpo.append(f"""<section class="secao secao--clara">
  <div class="env">
    <div class="grade grade--2">{card_evento_agro(destaque, destaque=True)}</div>
  </div>
</section>""")

        if resto:
            grupos = agrupar_eventos_por_mes(resto)
            blocos_mes = "".join(f"""<div class="agenda-mes">
  <h3 class="agenda-mes__titulo">{e(rotulo)}</h3>
  <div class="grade grade--3">{''.join(card_evento_agro(ev) for ev in eventos)}</div>
</div>""" for rotulo, eventos in grupos)

            corpo.append(f"""<section class="secao">
  <div class="env">
    <div class="cabeca-secao"><p class="olho">Calendário completo</p><h2>Próximas feiras e eventos do agronegócio brasileiro</h2></div>
    {blocos_mes}
  </div>
</section>""")
    else:
        corpo.append(f'<section class="secao"><div class="env"><div class="vazio">'
                     f'<h2>{e(s.get("vazio_titulo", "Nenhum evento confirmado no momento"))}</h2>'
                     f'<p>{e(s.get("vazio_texto", ""))}</p></div></div></section>')

    corpo.append(cta_faixa(cfg, "Vai estar em alguma dessas feiras?",
                           "Aproveite para conhecer as oportunidades da Prime Fazendas antes do evento."))

    ld_migalha = ld_breadcrumbs(cfg, [("Início", "/"), ("Agenda Agro", "/agenda-agro/")])

    return pagina(cfg, titulo=s.get("titulo", "Agenda Agro"),
                  descricao=s.get("descricao_meta", s.get("chamada", "")),
                  url="/agenda-agro/", corpo="\n".join(corpo), json_ld=[ld_migalha],
                  hreflang=hreflang_para(cfg, "/agenda-agro/"))


def gerar_post(cfg, p, outros) -> str:
    capa_html = ""
    if preenchido(p.get('capa')):
        capa_html = (
            '<section class="secao secao--compacta secao--sem-topo"><div class="env">'
            '<div class="artigo"><figure class="artigo__capa">'
            f'<img src="{e(p["capa"])}" alt="{e(p["titulo"])}" loading="lazy" width="1200" height="675">'
            '<figcaption>Imagem ilustrativa — acervo Prime Fazendas</figcaption>'
            '</figure></div></div></section>'
        )

    corpo = [f"""<section class="secao secao--compacta">
  <div class="env">
    <div class="artigo">
      {migalhas([("Início", "/"), ("Notícias", "/blog/"), (p['titulo'], "")])}
      <p class="artigo__meta"><span class="post-card__cat">{e(p['categoria'])}</span>
      <span>·</span><time datetime="{p['data'].isoformat()}">{e(fmt_data(p['data']))}</time>
      <span>·</span><span>{e(p['autor'])}</span>
      {f"<span>·</span><span>{p['tempo_leitura']} min de leitura</span>" if p.get('tempo_leitura') else ''}</p>
      <h1>{e(p['titulo'])}</h1>
      {f'<p class="chamada chamada--larga">{e(p["resumo"])}</p>' if p.get('resumo') else ''}
    </div>
  </div>
</section>
{capa_html}
<section class="secao secao--compacta">
  <div class="env">
    <article class="artigo prosa artigo__corpo">{p['html']}</article>
  </div>
</section>"""]

    relacionados = [o for o in outros if o["slug"] != p["slug"]][:2]
    if relacionados:
        corpo.append(f"""<section class="secao secao--clara">
  <div class="env">
    <div class="cabeca-secao"><p class="olho">Continue lendo</p></div>
    <div class="grade-posts">{''.join(card_post(o) for o in relacionados)}</div>
  </div>
</section>""")

    corpo.append(cta_faixa(cfg, "Tem uma propriedade ou uma dúvida?",
                           "Fale com quem negocia terra no Tocantins todos os dias."))

    dominio = cfg["site"]["dominio"].rstrip("/")
    ld = json.dumps({
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": p["titulo"],
        "description": p.get("resumo", ""),
        "datePublished": p["data"].isoformat(),
        "dateModified": p["data"].isoformat(),
        **({"image": dominio + p["capa"]} if preenchido(p.get("capa")) else {}),
        "author": {"@type": "Organization", "name": p["autor"]},
        "publisher": {"@type": "Organization", "name": cfg["marca"]["nome"]},
        "mainEntityOfPage": dominio + p["url"],
    }, ensure_ascii=False)
    ld_migalha = ld_breadcrumbs(cfg, [("Início", "/"), ("Notícias", "/blog/"), (p["titulo"], p["url"])])

    og_img_post = (dominio + p["capa"]) if preenchido(p.get("capa")) else ""

    return pagina(cfg, titulo=p["titulo"], descricao=p.get("resumo", ""), url=p["url"],
                  corpo="\n".join(corpo), og_tipo="article", json_ld=[ld, ld_migalha],
                  rascunho=bool(p.get("_rascunho")), og_imagem=og_img_post,
                  hreflang=hreflang_para(cfg, p["url"]))


def gerar_contato(cfg, pag) -> str:
    s = pag.get("contato", {})
    c = cfg["contato"]

    corpo = [hero(cfg, olho="Contato", titulo=s.get("titulo", "Contato e consultoria"),
                  texto=s.get("chamada", ""), interno=True, foto="/midia/imoveis/fazenda-rubi-negro/foto-07.jpg")]

    numero_zap = re.sub(r"\D", "", str(c.get("whatsapp_numero_internacional") or "")) \
        if preenchido(c.get("whatsapp_numero_internacional")) else ""
    endpoint_lead = cfg.get("formulario", {}).get("endpoint", "")

    form = f"""<form class="form" data-modo="whatsapp" data-whatsapp="{e(numero_zap)}"{f' data-endpoint="{e(endpoint_lead)}"' if preenchido(endpoint_lead) else ''}>
  <input type="text" name="_honey" style="display:none" tabindex="-1" autocomplete="off">
  <input type="hidden" name="_subject" value="Novo lead — site Prime Fazendas">
  <input type="hidden" name="_template" value="table">
  <input type="hidden" name="_captcha" value="false">
  <div class="campo--duplo">
    <div class="campo">
      <label for="nome">Nome <span class="req">*</span></label>
      <input type="text" id="nome" name="nome" required autocomplete="name">
    </div>
    <div class="campo">
      <label for="email">E-mail <span class="req">*</span></label>
      <input type="email" id="email" name="email" required autocomplete="email">
    </div>
  </div>
  <div class="campo">
    <label for="telefone">Telefone / WhatsApp</label>
    <input type="tel" id="telefone" name="telefone" autocomplete="tel">
  </div>
  <div class="campo--duplo">
    <div class="campo">
      <label for="interesse">O que você busca</label>
      <select id="interesse" name="interesse">
        <option>Comprar uma propriedade</option>
        <option>Vender minha propriedade</option>
        <option>Arrendar uma propriedade (buscar terra)</option>
        <option>Tenho uma propriedade e quero oferecer para arrendamento</option>
        <option>Avaliar uma propriedade</option>
        <option>Regularização fundiária ou ambiental</option>
        <option>Investir no agro</option>
        <option>Outro assunto</option>
      </select>
    </div>
    <div class="campo">
      <label for="regiao">Região de interesse</label>
      <input type="text" id="regiao" name="regiao" placeholder="Ex: Palmas, Matopiba, Vale do Araguaia">
    </div>
  </div>
  <div class="campo--duplo">
    <div class="campo">
      <label for="empresa">Empresa / Grupo (se aplicável)</label>
      <input type="text" id="empresa" name="empresa" placeholder="Nome da empresa ou grupo, se houver">
    </div>
    <div class="campo">
      <label for="area_pretendida">Área pretendida ou disponível (ha)</label>
      <input type="text" id="area_pretendida" name="area_pretendida" placeholder="Ex: 500 a 2.000 ha">
    </div>
  </div>
  <div class="campo">
    <label for="investimento">Faixa de investimento</label>
    <select id="investimento" name="investimento">
      <option>Prefiro não informar</option>
      <option>Até R$ 5 milhões</option>
      <option>R$ 5 a 20 milhões</option>
      <option>R$ 20 a 50 milhões</option>
      <option>Acima de R$ 50 milhões</option>
    </select>
  </div>
  <div class="campo">
    <label for="mensagem">Mensagem</label>
    <textarea id="mensagem" name="mensagem" placeholder="Conte o que você procura: tamanho, aptidão, região, prazo."></textarea>
  </div>
  <div class="grupo-btn">
    <button class="btn btn--principal" type="submit">Enviar e falar no WhatsApp</button>
  </div>
  <p class="form__nota">{e(s.get('form_nota', '')) or 'Nome e e-mail bastam para registrarmos seu contato. Um dos nossos consultores vai falar com você — se preferir, informe também o telefone para agilizar o WhatsApp.'}</p>
  <p class="form__nota" data-retorno hidden role="status"></p>
</form>"""

    itens = []
    if preenchido(c.get("telefone")):
        tel = re.sub(r"\D", "", c.get("telefone_link") or c["telefone"])
        itens.append(("Telefone", f'<a href="tel:+{tel}">{e(formatar_telefone_exibicao(c, cfg.get("site", {}).get("idioma", "")))}</a>'))
    if preenchido(c.get("whatsapp")):
        zap = montar_url_zap(cfg)
        val = (f'<a href="{e(zap)}" target="_blank" rel="noopener">{e(formatar_telefone_exibicao(c, cfg.get("site", {}).get("idioma", "")))}</a>'
               if zap else e(c["whatsapp"]))
        itens.append(("WhatsApp", val))
    if preenchido(c.get("email")):
        itens.append(("E-mail", f'<a href="mailto:{e(c["email"])}">{e(c["email"])}</a>'))
    if preenchido(c.get("endereco")):
        itens.append(("Endereço", e(c["endereco"])))
    cidade = ", ".join(x for x in [c.get("cidade"), c.get("estado")] if preenchido(x))
    if cidade:
        itens.append(("Onde estamos", e(cidade)))
    if preenchido(c.get("horario")):
        itens.append(("Atendimento", e(c["horario"])))
    if preenchido(c.get("creci")):
        itens.append(("CRECI", e(c["creci"])))

    lado = "".join(
        f'<div class="contato-item"><p class="contato-item__rot">{e(r)}</p>'
        f'<p class="contato-item__val">{v}</p></div>'
        for r, v in itens
    ) or '<div class="contato-item"><p class="contato-item__val">Dados de contato em atualização.</p></div>'

    corpo.append(f"""<section class="secao">
  <div class="env">
    <div class="contato-grade">
      <div>
        <h2>{e(s.get('form_titulo', 'Fale com um especialista'))}</h2>
        <p class="chamada chamada--larga" style="margin-bottom:2.25rem">{e(s.get('intro', ''))}</p>
        {form}
      </div>
      <div>
        <p class="olho">Canais diretos</p>
        {lado}
      </div>
    </div>
  </div>
</section>""")

    local_mapa = ", ".join(x for x in [c.get("cidade"), c.get("estado"), c.get("pais")] if preenchido(x))
    if local_mapa:
        corpo.append(f"""<section class="secao secao--compacta">
  <div class="env">
    <div class="bloco-ficha">
      <h3>Onde estamos</h3>
      <div class="mapa">
        <iframe src="https://www.google.com/maps?q={url_quote(local_mapa)}&output=embed"
                title="Mapa — {e(local_mapa)}" loading="lazy"
                referrerpolicy="no-referrer-when-downgrade"></iframe>
      </div>
    </div>
  </div>
</section>""")

    ld_migalha = ld_breadcrumbs(cfg, [("Início", "/"), ("Contato", "/contato/")])

    return pagina(cfg, titulo=s.get("titulo", "Contato"),
                  descricao=s.get("descricao_meta", s.get("chamada", "")),
                  url="/contato/", corpo="\n".join(corpo), json_ld=[ld_migalha],
                  hreflang=hreflang_para(cfg, "/contato/"))


def gerar_404(cfg) -> str:
    corpo = [f"""<section class="secao">
  <div class="env centro" style="padding-block:clamp(3rem,10vw,6rem)">
    <p class="olho olho--centro">Erro 404</p>
    <h1>Esta página não existe</h1>
    <p class="chamada chamada--larga" style="margin-inline:auto">
      O endereço pode ter mudado ou a propriedade que você procurava já foi negociada.
    </p>
    <div class="grupo-btn" style="justify-content:center;margin-top:2.25rem">
      <a class="btn btn--principal" href="/">Ir para o início</a>
      <a class="btn btn--vazado" href="/imoveis/">Ver imóveis</a>
    </div>
  </div>
</section>"""]
    return pagina(cfg, titulo="Página não encontrada", descricao="Página não encontrada.",
                  url="/404.html", corpo="\n".join(corpo), robots="noindex, follow")



def bloco_manutencao(man: dict) -> str:
    """Diretivas de autenticacao basica que vao para o topo do .htaccess."""
    caminho = man["caminho_no_servidor"].rstrip("/")
    mensagem = man.get("mensagem_navegador") or "Area restrita"
    return f"""
# ---------------------------------------------------------------------------
# MODO MANUTENCAO ATIVO
# O site inteiro exige usuario e senha. Para liberar ao publico:
#     .\\manutencao.ps1 -Desativar
#     depois gere a saida e deixe a Vercel publicar pelo main
# ---------------------------------------------------------------------------
AuthType Basic
AuthName "{mensagem}"
AuthUserFile {caminho}/.htpasswd
Require valid-user

"""


HTACCESS = """# Prime Fazendas — configuração de servidor (Apache / site estatíco)

# HTTPS obrigatório
<IfModule mod_rewrite.c>
  RewriteEngine On
  RewriteCond %{HTTPS} !=on
  RewriteCond %{HTTP:X-Forwarded-Proto} !https
  RewriteRule ^(.*)$ https://%{HTTP_HOST}/$1 [R=301,L]

  # sem www
  RewriteCond %{HTTP_HOST} ^www\\.(.+)$ [NC]
  RewriteRule ^(.*)$ https://%1/$1 [R=301,L]
</IfModule>

ErrorDocument 404 /404.html

# Compressão
<IfModule mod_deflate.c>
  AddOutputFilterByType DEFLATE text/html text/css text/plain text/xml application/javascript application/json image/svg+xml
</IfModule>

# Cache dos estáticos
<IfModule mod_expires.c>
  ExpiresActive On
  ExpiresByType text/css "access plus 1 year"
  ExpiresByType application/javascript "access plus 1 year"
  ExpiresByType image/jpeg "access plus 6 months"
  ExpiresByType image/png "access plus 6 months"
  ExpiresByType image/webp "access plus 6 months"
  ExpiresByType image/svg+xml "access plus 6 months"
  ExpiresByType text/html "access plus 0 seconds"
</IfModule>

# Segurança
<IfModule mod_headers.c>
  Header set X-Content-Type-Options "nosniff"
  Header set Referrer-Policy "strict-origin-when-cross-origin"
  Header set X-Frame-Options "SAMEORIGIN"
  Header set Permissions-Policy "geolocation=(), microphone=(), camera=()"
</IfModule>

<IfModule mod_autoindex.c>
  Options -Indexes
</IfModule>

# O proprio arquivo de senhas nunca pode ser servido pela web
<FilesMatch "^\\.(htaccess|htpasswd)$">
  Require all denied
</FilesMatch>
"""


# ================================================================== build ==

_RE_IMG_MIDIA = re.compile(r'<img\b([^>]*?)src="(/midia/[^"]+)\.(jpg|jpeg|png)"([^>]*?)>')


def _webp_existe(caminho_sem_extensao: str) -> bool:
    """Confere se existe uma versao .webp gerada ao lado do arquivo original
    em conteudo/midia/. Usado para so oferecer o formato quando ele realmente
    compensa (ver script de otimizacao de imagens)."""
    caminho = CONTEUDO / "midia" / (caminho_sem_extensao[len("/midia/"):] + ".webp")
    return caminho.exists()


def _envolver_imagens_com_webp(html_pagina: str) -> str:
    """Envolve toda <img src="/midia/....jpg|.png"> que tenha uma versao .webp
    mais leve com um <picture><source type="image/webp">, mantendo a tag
    <img> original como fallback (mesmo src, mesmos atributos) para
    navegadores antigos e para o crawler que so olhar o <img>."""

    def _sub(m: re.Match) -> str:
        antes, caminho, ext, depois = m.group(1), m.group(2), m.group(3), m.group(4)
        tag_original = f'<img {antes}src="{caminho}.{ext}"{depois}>'
        if not _webp_existe(caminho):
            return tag_original
        return (
            f'<picture><source srcset="{caminho}.webp" type="image/webp">'
            f'{tag_original}</picture>'
        )

    return _RE_IMG_MIDIA.sub(_sub, html_pagina)


def escrever(caminho_rel: str, conteudo: str) -> None:
    destino = SAIDA / caminho_rel
    destino.parent.mkdir(parents=True, exist_ok=True)
    if caminho_rel.endswith(".html"):
        conteudo = _envolver_imagens_com_webp(conteudo)
    destino.write_text(conteudo, encoding="utf-8", newline="\n")


def auditar(cfg: dict, imoveis: list, posts: list, dados_agro: dict, depoimentos: dict) -> None:
    """Checagens que o fluxo de publicacao usa para decidir se pode seguir."""
    for grupo in ("contato", "redes", "comunidade"):
        for chave, valor in (cfg.get(grupo) or {}).items():
            if chave.startswith("_"):
                continue
            if str(valor).strip() == PENDENTE:
                aviso(f"config.json → {grupo}.{chave} ainda está em {PENDENTE}.")

    if MOSTRAR_RASCUNHOS:
        n_r = sum(1 for i in imoveis if i.get("_rascunho")) + sum(1 for p in posts if p.get("_rascunho"))
        aviso(f"MODO RASCUNHO (--demo): {n_r} item(ns) nao publicado(s) estao aparecendo. "
              f"Isso e so para voce ver o layout — o fluxo de publicacao ignora este modo.")

    # Dado de teste que escapa para o ar e pior do que campo vazio: telefone que
    # ninguem atende perde lead, e CRECI falso e numero de registro regulado —
    # publicar um inventado expoe a empresa a sancao administrativa.
    suspeitos = []
    for chave in ("telefone", "telefone_link", "whatsapp",
                  "whatsapp_numero_internacional", "creci"):
        valor = (cfg.get("contato") or {}).get(chave)
        if not preenchido(valor):
            continue
        digitos = re.sub(r"[^0-9]", "", str(valor))
        if len(digitos) < 4:
            continue
        motivo = ""
        if re.search(r"(\d)\1{4,}", digitos):
            motivo = "o mesmo digito repetido 5 vezes ou mais"
        elif re.search(r"01234|12345|23456|34567|45678|98765|87654", digitos):
            motivo = "sequencia numerica obvia"
        if motivo:
            suspeitos.append(f"contato.{chave} = {valor} ({motivo})")

    if suspeitos:
        bloqueio(
            "dados de contato aparentemente ficticios em conteudo/config.json "
            "(contato.telefone, contato.telefone_link, contato.whatsapp, "
            "contato.whatsapp_numero_internacional, contato.creci): "
            + "; ".join(suspeitos)
            + ". Troque pelos reais antes de publicar."
        )

    exemplos = [i["arquivo"] for i in imoveis if i.get("_exemplo") and not i.get("_rascunho")]
    if exemplos:
        bloqueio("imóveis de EXEMPLO publicados: " + ", ".join(exemplos)
                 + ". Troque pelos dados reais ou marque publicado=false antes de subir.")

    suspeita_preco = []
    for i in imoveis:
        if i.get("preco_sob_consulta") or not i.get("preco"):
            continue
        preco_ha = i.get("preco_ha") or 0
        if preco_ha and preco_ha < 1000:
            suspeita_preco.append(
                f"{i.get('arquivo', i.get('slug', 'imóvel'))} → {fmt_num(round(preco_ha))}/ha"
            )
    if suspeita_preco:
        aviso(
            "preço por hectare muito abaixo do esperado em: "
            + "; ".join(suspeita_preco)
            + ". Confirme área, moeda e disponibilidade antes de publicar."
        )

    nao_verif = [i.get("rotulo", "?") for i in dados_agro.get("indicadores", []) if i.get("verificar")]
    if nao_verif:
        aviso(f"{len(nao_verif)} indicador(es) em dados-agro.json com verificar=true — "
              f"não estão sendo exibidos no site até você confirmar a fonte.")

    if not imoveis:
        aviso("nenhum imóvel publicado — a página /imoveis/ vai mostrar o estado 'em atualização'.")
    if not posts:
        aviso("nenhum post publicado — /blog/ vai mostrar 'em breve'.")

    if not any(d.get("publicado") for d in depoimentos.get("depoimentos", [])):
        aviso("nenhum depoimento publicado — a seção de prova social não aparece na home.")


def main() -> int:
    apenas_auditar = "--auditar" in sys.argv

    cfg = limpar_meta(ler_json(CONTEUDO / "config.json"))
    for grupo in ("marca", "site", "contato", "redes", "comunidade", "formulario", "analytics", "rodape"):
        if isinstance(cfg.get(grupo), dict):
            cfg[grupo] = limpar_meta(cfg[grupo])
    pag = limpar_meta(ler_json(CONTEUDO / "paginas.json"))
    dados_agro = limpar_meta(ler_json(CONTEUDO / "dados-agro.json"))
    depoimentos = limpar_meta(ler_json(CONTEUDO / "depoimentos.json"))

    if bloqueios:
        relatar(0)
        return 1

    cfg.setdefault("rodape", pag.get("rodape", {}))
    if not cfg.get("rodape"):
        cfg["rodape"] = pag.get("rodape", {})

    manutencao = carregar_manutencao()
    imoveis = carregar_imoveis()
    imoveis_i18n_map = ler_json(CONTEUDO / "imoveis_i18n.json") or {}
    registrar_imoveis_traduzidos(imoveis, imoveis_i18n_map)
    posts = carregar_posts()
    noticias_i18n_map = ler_json(CONTEUDO / "noticias_i18n.json") or {}
    for p in posts:
        if p["slug"] in noticias_i18n_map:
            PAGINAS_TRADUZIDAS[p["url"]] = {
                "en": f"/en/blog/{p['slug']}/",
                "zh": f"/zh/blog/{p['slug']}/",
            }
    agenda_agro = carregar_agenda_agro()

    auditar(cfg, imoveis, posts, dados_agro, depoimentos)

    if apenas_auditar:
        relatar(0)
        return 1 if bloqueios else 0

    # limpa a saída, preservando o .git se alguém apontar para lá por engano
    if SAIDA.exists():
        for item in SAIDA.iterdir():
            if item.name == ".git":
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
    SAIDA.mkdir(parents=True, exist_ok=True)

    # estáticos
    shutil.copytree(TEMA / "assets", SAIDA / "assets", dirs_exist_ok=True)

    midia = CONTEUDO / "midia"
    if midia.exists():
        shutil.copytree(midia, SAIDA / "midia", dirs_exist_ok=True)

    # páginas
    escrever("index.html", gerar_home(cfg, pag, imoveis, posts, dados_agro, depoimentos))
    escrever("sobre/index.html", gerar_sobre(cfg, pag))
    escrever("servicos/index.html", gerar_servicos(cfg, pag))
    escrever("data-center/index.html", gerar_datacenter(cfg, pag))
    escrever("en/data-center/index.html", gerar_datacenter_i18n(cfg, pag.get("datacenter_en", {}), "en"))
    escrever("zh/data-center/index.html", gerar_datacenter_i18n(cfg, pag.get("datacenter_zh", {}), "zh"))
    for lang in ("en", "zh"):
        escrever(f"{lang}/index.html", gerar_home_i18n(cfg, pag.get(f"home_{lang}", {}), lang))
        escrever(f"{lang}/sobre/index.html", gerar_sobre_i18n(cfg, pag.get(f"sobre_{lang}", {}), lang))
        escrever(f"{lang}/servicos/index.html", gerar_servicos_i18n(cfg, pag.get(f"servicos_{lang}", {}), lang))
        escrever(f"{lang}/contato/index.html", gerar_contato_i18n(cfg, pag.get(f"contato_{lang}", {}), lang))
        escrever(f"{lang}/agenda-agro/index.html", gerar_agenda_agro_i18n(cfg, pag.get(f"agenda_agro_{lang}", {}), lang))
    escrever("investir-no-agro/index.html", gerar_investir(cfg, pag, dados_agro))
    dados_agro_i18n = {
        "en": {"argumentos_investimento": dados_agro.get("argumentos_investimento_en", []),
               "indicadores": dados_agro.get("indicadores_en", []),
               "fatores_regiao": dados_agro.get("fatores_regiao_en", [])},
        "zh": {"argumentos_investimento": dados_agro.get("argumentos_investimento_zh", []),
               "indicadores": dados_agro.get("indicadores_zh", []),
               "fatores_regiao": dados_agro.get("fatores_regiao_zh", [])},
    }
    for lang in ("en", "zh"):
        escrever(f"{lang}/investir-no-agro/index.html",
                 gerar_investir_i18n(cfg, pag.get(f"investir_{lang}", {}), lang, dados_agro_i18n[lang]))
    escrever("imoveis/index.html", gerar_lista_imoveis(cfg, pag, imoveis))
    for lang in ("en", "zh"):
        escrever(f"{lang}/imoveis/index.html", gerar_lista_imoveis_i18n(cfg, imoveis, lang, imoveis_i18n_map))
    escrever("comunidade/index.html", gerar_redirect(cfg, "/blog/"))
    escrever("blog/index.html", gerar_blog(cfg, pag, posts, imoveis))
    for lang in ("en", "zh"):
        escrever(f"{lang}/blog/index.html", gerar_blog_i18n(cfg, posts, imoveis, lang, noticias_i18n_map, imoveis_i18n_map))
    escrever("agenda-agro/index.html", gerar_agenda_agro(cfg, pag, agenda_agro))
    escrever("contato/index.html", gerar_contato(cfg, pag))
    escrever("404.html", gerar_404(cfg))

    for im in imoveis:
        escrever(f"imoveis/{im['slug']}/index.html", gerar_ficha_imovel(cfg, im, imoveis))
        if im["slug"] in imoveis_i18n_map:
            for lang in ("en", "zh"):
                escrever(f"{lang}/imoveis/{im['slug']}/index.html",
                         gerar_ficha_imovel_i18n(cfg, im, imoveis, lang, imoveis_i18n_map))
    for p in posts:
        escrever(f"blog/{p['slug']}/index.html", gerar_post(cfg, p, posts))
        if p["slug"] in noticias_i18n_map:
            for lang in ("en", "zh"):
                escrever(f"{lang}/blog/{p['slug']}/index.html",
                         gerar_post_i18n(cfg, p, posts, lang, noticias_i18n_map))

    # sitemap + robots + htaccess
    dominio = cfg["site"]["dominio"].rstrip("/")
    urls = ["/", "/sobre/", "/servicos/", "/data-center/", "/investir-no-agro/", "/imoveis/",
            "/blog/", "/agenda-agro/", "/contato/"]
    for lang in ("en", "zh"):
        urls += [f"/{lang}/", f"/{lang}/sobre/", f"/{lang}/servicos/", f"/{lang}/data-center/",
                 f"/{lang}/contato/", f"/{lang}/agenda-agro/", f"/{lang}/imoveis/", f"/{lang}/blog/",
                 f"/{lang}/investir-no-agro/"]
        urls += [f"/{lang}/imoveis/{slug}/" for slug in imoveis_i18n_map]
        urls += [f"/{lang}/blog/{slug}/" for slug in noticias_i18n_map]
    urls += [im["url"] for im in imoveis]
    urls += [p["url"] for p in posts]
    hoje = date.today().isoformat()
    entradas = "".join(
        f"<url><loc>{dominio}{u}</loc><lastmod>{hoje}</lastmod>"
        f"<priority>{'1.0' if u == '/' else '0.8' if u.count('/') <= 2 else '0.6'}</priority></url>"
        for u in urls
    )
    escrever("sitemap.xml",
             '<?xml version="1.0" encoding="UTF-8"?>\n'
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
             + entradas + "</urlset>\n")
    # Sob manutencao o site nao deve ser indexado: se o Google visitar durante a
    # obra e receber 401, corre o risco de derrubar as paginas do indice.
    if manutencao.get("ativa"):
        escrever("robots.txt", "User-agent: *\nDisallow: /\n")
    else:
        robots_txt = (
            "User-agent: *\n"
            "Allow: /\n"
            "\n"
            "# Crawlers de IA / LLM — liberados explicitamente (GEO)\n"
            "User-agent: GPTBot\n"
            "Allow: /\n"
            "\n"
            "User-agent: ChatGPT-User\n"
            "Allow: /\n"
            "\n"
            "User-agent: ClaudeBot\n"
            "Allow: /\n"
            "\n"
            "User-agent: Claude-User\n"
            "Allow: /\n"
            "\n"
            "User-agent: PerplexityBot\n"
            "Allow: /\n"
            "\n"
            "User-agent: CCBot\n"
            "Allow: /\n"
            "\n"
            "User-agent: Google-Extended\n"
            "Allow: /\n"
            "\n"
            f"Sitemap: {dominio}/sitemap.xml\n"
        )
        escrever("robots.txt", robots_txt)

    # IndexNow — arquivo de posse da chave na raiz do site (indexnow.org).
    # Bing, Yandex e outros usam esse arquivo pra validar os pings de URL nova/atualizada.
    # So publicado fora de manutencao, junto com o robots.txt liberado.
    indexnow_key = cfg.get("seo", {}).get("indexnow_key")
    if indexnow_key and not manutencao.get("ativa"):
        escrever(f"{indexnow_key}.txt", indexnow_key)

    # llms.txt — resumo estruturado do site para crawlers e agentes de IA
    # (ChatGPT, Perplexity, Claude etc.), no padrao emergente https://llmstxt.org/.
    # So gerado fora de manutencao, junto com o robots.txt liberado.
    if not manutencao.get("ativa"):
        marca = cfg["marca"]
        contato = cfg["contato"]
        imoveis_disp = [im for im in imoveis if im.get("status") == "disponivel" and not im.get("_rascunho") and not im.get("_exemplo")]
        categorias_posts = sorted({p["categoria"] for p in posts if p.get("categoria")})
        linhas = [
            f"# {marca['nome']}",
            "",
            f"> {marca.get('descricao_curta', cfg['site'].get('descricao_padrao', ''))}",
            "",
            f"Imobiliária rural especializada em fazendas no Tocantins e no Matopiba (Brasil). "
            f"Fundada em {marca.get('ano_fundacao', '')} por {marca.get('fundador', '')}. "
            f"CRECI {contato.get('creci', '')}. Sede em {contato.get('cidade', '')}, {contato.get('estado', '')}.",
            "",
            "## Portfólio",
            "",
            f"- [Imóveis à venda]({dominio}/imoveis/): {len(imoveis_disp)} fazendas disponíveis, com área total, "
            "preço, documentação e disponibilidade hídrica detalhados por ficha.",
            f"- [Data Center]({dominio}/data-center/): estruturação de terrenos e ativos para data centers "
            "hyperscale no Tocantins/Matopiba — energia, água, conectividade e modelos de projeto.",
            "",
            "## Notícias e insights",
            "",
            f"- [Blog]({dominio}/blog/): artigos objetivos sobre mercado de terras, jurídico, financiamento, "
            "recursos hídricos, exportação e regularização fundiária no Matopiba. "
            f"Categorias cobertas hoje: {', '.join(categorias_posts)}.",
            "",
            "## Institucional",
            "",
            f"- [Sobre nós]({dominio}/sobre/)",
            f"- [Serviços]({dominio}/servicos/)",
            f"- [Investir no agronegócio]({dominio}/investir-no-agro/)",
            f"- [Agenda Agro]({dominio}/agenda-agro/)",
            f"- [Contato]({dominio}/contato/)",
            "",
            "## Contato",
            "",
            f"- E-mail: {contato.get('email', '')}",
            f"- WhatsApp: {contato.get('whatsapp', '')}",
            "",
            "## English",
            "",
            f"- [Home (English)]({dominio}/en/): farm listings, services and the Data Center "
            "division are also available in English, with the same photos, prices and technical "
            "data as the Portuguese pages.",
            f"- [Farms for sale (English)]({dominio}/en/imoveis/): all {len(imoveis_disp)} available "
            "farms, translated in full — description, features, infrastructure and documentation.",
            f"- [News (English)]({dominio}/en/blog/): the full news archive translated into English, "
            "covering land market, legal, financing, water resources, exports and land regularization "
            f"topics for the Matopiba region. Categories: {', '.join(sorted({CATEGORIA_I18N['en'].get(c, c) for c in categorias_posts}))}.",
            f"- [About us (English)]({dominio}/en/sobre/)",
            f"- [Services (English)]({dominio}/en/servicos/)",
            f"- [Data Center (English)]({dominio}/en/data-center/)",
            f"- [Invest in agribusiness (English)]({dominio}/en/investir-no-agro/)",
            f"- [Contact (English)]({dominio}/en/contato/)",
            "",
            "## 中文（简体）",
            "",
            f"- [首页（中文）]({dominio}/zh/)：农场房源、服务及数据中心业务板块同样提供中文版本，"
            "照片、价格及技术数据与葡萄牙语页面完全一致。",
            f"- [在售农场（中文）]({dominio}/zh/imoveis/)：全部{len(imoveis_disp)}处可售农场的完整中文译文——"
            "描述、特点、基础设施及文件资料。",
            f"- [新闻资讯（中文）]({dominio}/zh/blog/)：完整的新闻档案中文译文，涵盖马托皮巴地区的土地市场、"
            f"法律、融资、水资源、出口及土地合规等主题。分类：{'、'.join(sorted({CATEGORIA_I18N['zh'].get(c, c) for c in categorias_posts}))}。",
            f"- [关于我们（中文）]({dominio}/zh/sobre/)",
            f"- [服务项目（中文）]({dominio}/zh/servicos/)",
            f"- [数据中心（中文）]({dominio}/zh/data-center/)",
            f"- [投资农业（中文）]({dominio}/zh/investir-no-agro/)",
            f"- [联系我们（中文）]({dominio}/zh/contato/)",
        ]
        escrever("llms.txt", "\n".join(linhas) + "\n")

    htaccess = HTACCESS
    if manutencao.get("ativa"):
        htaccess = bloco_manutencao(manutencao) + HTACCESS
        escrever(".htpasswd", f"{manutencao['usuario']}:{manutencao['hash']}\n")
    escrever(".htaccess", htaccess)

    n = sum(1 for _ in SAIDA.rglob("*.html"))
    relatar(n, imoveis, posts)
    return 1 if bloqueios else 0


def relatar(n_html: int, imoveis=None, posts=None) -> None:
    print()
    print("=" * 68)
    print("  PRIME FAZENDAS — build")
    print("=" * 68)

    if n_html:
        print(f"  páginas geradas .... {n_html}")
        print(f"  imóveis ............ {len(imoveis or [])}")
        print(f"  artigos ............ {len(posts or [])}")
        try:
            destino = SAIDA.relative_to(RAIZ)
            destino_txt = f"{destino.as_posix()}/"
        except Exception:
            destino_txt = str(SAIDA)
        print(f"  saída .............. {destino_txt}")

    if avisos:
        print()
        print(f"  AVISOS ({len(avisos)}) — o site funciona, mas confira:")
        for a in avisos:
            print(f"    · {a}")

    if bloqueios:
        print()
        print(f"  BLOQUEIOS ({len(bloqueios)}) — resolva antes de publicar:")
        for b in bloqueios:
            print(f"    ! {b}")
    elif n_html:
        print()
        print("  Sem bloqueios. Pronto para publicar.")

    print("=" * 68)
    print()


if __name__ == "__main__":
    sys.exit(main())
