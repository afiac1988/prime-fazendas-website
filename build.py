#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prime Fazendas â€” gerador do site.

LÃª conteudo/ e escreve site/. Zero dependÃªncias: sÃ³ a biblioteca padrÃ£o do Python.

    python build.py                     gera o site
    python build.py --auditar            sÃ³ valida o conteÃºdo e sai (nÃ£o escreve nada)
    python build.py --demo --saida TMP   gera uma prÃ©via fora do site/

O que vocÃª edita fica em conteudo/. Este arquivo Ã© a mÃ¡quina; normalmente
vocÃª nÃ£o precisa abri-lo.
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

RAIZ = Path(__file__).resolve().parent
CONTEUDO = RAIZ / "conteudo"
TEMA = RAIZ / "tema"


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
        bloqueio(f"arquivo obrigatÃ³rio nÃ£o encontrado: {caminho.relative_to(RAIZ)}")
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
            f"coluna {e.colno}: {e.msg}. Provavelmente falta uma vÃ­rgula, "
            f"sobra uma vÃ­rgula no fim de uma lista, ou uma aspa nÃ£o foi fechada."
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
    """Remove as chaves de anotaÃ§Ã£o (que comeÃ§am com _)."""
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


def resumo_fator_regiao(texto: str, indice: int) -> tuple[str, str]:
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
    if texto in mapa:
        return mapa[texto]

    partes = texto.split()
    titulo = " ".join(partes[:2]).strip() if len(partes) >= 2 else texto[:24].strip()
    if not titulo:
        titulo = f"Item {indice:02d}"
    return titulo, texto


MESES = ["janeiro", "fevereiro", "marÃ§o", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]


def fmt_data(d: date) -> str:
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


TIPOS = {
    "agricola": "AgrÃ­cola",
    "pecuaria": "PecuÃ¡ria",
    "mista": "Mista",
    "reflorestamento": "Reflorestamento",
    "lazer": "Lazer",
}

STATUS = {
    "disponivel": ("DisponÃ­vel", "selo--azul"),
    "reservado": ("Reservado", "selo--dourado"),
    "vendido": ("Vendido", "selo--vendido"),
}


def slugificar(texto: str) -> str:
    t = str(texto).lower().strip()
    acentos = {"Ã¡": "a", "Ã ": "a", "Ã¢": "a", "Ã£": "a", "Ã¤": "a", "Ã©": "e", "Ãª": "e",
               "Ã¨": "e", "Ã­": "i", "Ã¬": "i", "Ã³": "o", "Ã´": "o", "Ãµ": "o", "Ã²": "o",
               "Ãº": "u", "Ã¹": "u", "Ã»": "u", "Ã¼": "u", "Ã§": "c", "Ã±": "n"}
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
    """Subconjunto de Markdown: h2-h4, listas, citaÃ§Ã£o, parÃ¡grafo, hr."""
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


# ========================================================== peÃ§as visuais ==

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

# Marca da Prime Fazendas: sol sobre os sulcos do plantio.
# O desenho vem de tema/assets/marca.svg, gerado por ferramentas/gerar_og.py a
# partir da mesma geometria da imagem de compartilhamento â€” logo do site e
# miniatura do WhatsApp sao o mesmo desenho, nunca divergem.
_MARCA_SVG = (TEMA / "assets" / "marca.svg").read_text(encoding="utf-8")     if (TEMA / "assets" / "marca.svg").exists() else ""

if not _MARCA_SVG:
    aviso("tema/assets/marca.svg nao encontrado â€” rode: python ferramentas/gerar_og.py")


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


SVG_SELO = f'<span class="marca__disco">{svg_marca()}</span>'
SVG_SELO_RODAPE = f'<span class="marca__disco">{svg_marca(ident="pfr")}</span>'

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


def cabecalho(cfg: dict, url_atual: str) -> str:
    itens = []
    for item in cfg.get("navegacao", []):
        atual = ' aria-current="page"' if item["url"] == url_atual else ""
        itens.append(f'<a href="{e(item["url"])}"{atual}>{e(item["titulo"])}</a>')

    zap = montar_url_zap(cfg)
    cta_mobile = ""
    if zap:
        cta_mobile = f'<a class="btn btn--principal btn--bloco" href="{e(zap)}" target="_blank" rel="noopener">Falar no WhatsApp</a>'

    cta_topo = (
        f'<a class="btn btn--principal" href="{e(zap)}" target="_blank" rel="noopener">Falar no WhatsApp</a>'
        if zap else
        '<a class="btn btn--principal" href="/contato/">Fale com um especialista</a>'
    )

    return f"""<header class="topo">
  <div class="env topo__int">
    <a class="marca" href="/" aria-label="{e(cfg['marca']['nome'])} â€” pÃ¡gina inicial">
      {SVG_SELO}
      <span class="marca__txt">
        <span class="marca__nome">{e(cfg['marca']['nome'])}</span>
        <span class="marca__sub">ImÃ³veis Rurais</span>
      </span>
    </a>
    <nav class="nav" id="nav-principal" aria-label="NavegaÃ§Ã£o principal">
      {''.join(itens)}
      {cta_mobile}
    </nav>
    <div class="topo__acao">
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
          <span class="marca__sub">ImÃ³veis Rurais</span></span>
        </a>
        {f'<p class="rodape__tagline">{e(cfg["marca"]["tagline"])}</p>' if preenchido(cfg['marca'].get('tagline')) else ''}
        <p class="rodape__sobre">{e(rod.get('sobre_curto', ''))}</p>
        {redes}
      </div>
      <div>
        <h4>NavegaÃ§Ã£o</h4>
        <ul class="rodape__lista">{nav}</ul>
      </div>
      <div>
        <h4>Contato</h4>
        <ul class="rodape__lista">{''.join(linhas) or '<li>Em atualizaÃ§Ã£o</li>'}</ul>
      </div>
      <div>
        <h4>{e(cfg.get('comunidade', {}).get('nome', 'Comunidade'))}</h4>
        <ul class="rodape__lista">
          <li><a href="/comunidade/">Entrar na comunidade</a></li>
          <li><a href="/blog/">Blog e insights</a></li>
          <li><a href="/imoveis/">ImÃ³veis Ã  venda</a></li>
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
           og_tipo: str = "website", json_ld: str = "", rascunho: bool = False) -> str:
    site = cfg["site"]
    dominio = site["dominio"].rstrip("/")
    canonica = dominio + url
    titulo_completo = titulo if titulo == site["titulo_padrao"] else f"{titulo} | {cfg['marca']['nome']}"

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
        faixa = ('<div class="aviso-rascunho">PrÃ©-visualizaÃ§Ã£o local â€” este conteÃºdo contÃ©m '
                 'dados de exemplo e nÃ£o deve ir ao ar.</div>')

    ld = f'<script type="application/ld+json">{json_ld}</script>' if json_ld else ""

    return f"""<!DOCTYPE html>
<html lang="{e(site.get('idioma', 'pt-BR'))}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(titulo_completo)}</title>
<meta name="description" content="{e(descricao)}">
<link rel="canonical" href="{e(canonica)}">
<meta name="robots" content="index, follow">
<meta name="theme-color" content="#0C1E33">
<meta property="og:type" content="{e(og_tipo)}">
<meta property="og:site_name" content="{e(cfg['marca']['nome'])}">
<meta property="og:title" content="{e(titulo)}">
<meta property="og:description" content="{e(descricao)}">
<meta property="og:url" content="{e(canonica)}">
<meta property="og:locale" content="pt_BR">
<meta property="og:image" content="{e(dominio + site.get('og_imagem', ''))}">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/assets/favicon.svg">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cinzel:wght@500;600&family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600&family=Inter:wght@400;500;600;700&display=swap">
<link rel="stylesheet" href="/assets/estilo.css">
{ld}
{ga}
</head>
<body>
{faixa}
<a class="pular" href="#principal">Ir para o conteÃºdo</a>
{cabecalho(cfg, url)}
<main id="principal">
{corpo}
</main>
{rodape(cfg)}
{botao_zap}
<script src="/assets/site.js" defer></script>
</body>
</html>
"""


def hero(cfg: dict, *, olho: str, titulo: str, texto: str = "", botoes: str = "",
         interno: bool = False, foto: str = "") -> str:
    classe = "hero hero--interno" if interno else "hero"
    img = f'<img class="hero__foto" src="{e(foto)}" alt="" loading="eager">' if foto else ""
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
    return f'<nav class="migalhas" aria-label="Trilha de navegaÃ§Ã£o">{"".join(partes)}</nav>'


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


# =============================================================== conteÃºdo ==

def carregar_manutencao() -> dict:
    """
    Le manutencao.local.json (fora do versionamento). Quando ativo, o site
    inteiro fica atras de autenticacao HTTP do Apache â€” o servidor nao entrega
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


def carregar_imoveis() -> list[dict]:
    itens = []
    pasta = CONTEUDO / "imoveis"
    if not pasta.exists():
        return itens

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
            aviso(f"{arq.name}: sem tÃ­tulo â€” imÃ³vel ignorado.")
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
        d["fotos_url"] = [f"/midia/imoveis/{pasta_fotos}/{f}" for f in (d.get("fotos") or [])]
        for f in (d.get("fotos") or []):
            origem = CONTEUDO / "midia" / "imoveis" / pasta_fotos / f
            if not origem.exists():
                aviso(f"{arq.name}: a foto '{f}' nÃ£o existe em conteudo/midia/imoveis/{pasta_fotos}/")

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
            aviso(f"{arq.name}: sem 'titulo' no cabeÃ§alho â€” post ignorado.")
            continue

        try:
            d = datetime.strptime(str(meta.get("data", "")).strip(), "%Y-%m-%d").date()
        except ValueError:
            aviso(f"{arq.name}: data ausente ou fora do formato AAAA-MM-DD. Usando hoje.")
            d = date.today()

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
            "arquivo": arq.name,
            "_rascunho": rascunho,
        })

    posts.sort(key=lambda p: p["data"], reverse=True)
    return posts


# ================================================================ pÃ¡ginas ==

def card_imovel(im: dict) -> str:
    selos = []
    rotulo, classe = STATUS.get(im.get("status", "disponivel"), STATUS["disponivel"])
    if im.get("status") != "disponivel":
        selos.append(f'<span class="selo {classe}">{e(rotulo)}</span>')
    if im.get("certificacao_ambiental"):
        selos.append('<span class="selo">DocumentaÃ§Ã£o verificada</span>')
    if im.get("_rascunho"):
        selos.append('<span class="selo selo--aviso">Rascunho â€” nÃ£o publicado</span>')
    if im.get("_exemplo"):
        selos.append('<span class="selo selo--aviso">Exemplo</span>')

    if im["fotos_url"]:
        capa = (f'<a class="imovel__capa-link" href="{e(im["fotos_url"][0])}" target="_blank" rel="noopener noreferrer" title="Abrir foto em nova aba">'
                f'<img src="{e(im["fotos_url"][0])}" alt="{e(im["titulo"])}" loading="lazy">'
                f'</a>')
    else:
        capa = SVG_CAPA

    local = ", ".join(x for x in [im.get("municipio"), im.get("estado")] if x)
    tipo = TIPOS.get(im.get("tipo", ""), "")
    cabeca = " Â· ".join(x for x in [local, tipo] if x)

    dados = []
    if im.get("area_total_ha"):
        dados.append(f'<div class="dado"><span class="dado__rot">Ãrea total</span>'
                     f'<span class="dado__val">{fmt_num(im["area_total_ha"])} ha</span></div>')
    if im.get("preco_sob_consulta") or not im.get("preco"):
        dados.append('<div class="dado"><span class="dado__rot">Valor</span>'
                     '<span class="dado__val dado__val--preco">Sob consulta</span></div>')
    else:
        dados.append(f'<div class="dado"><span class="dado__rot">Valor</span>'
                     f'<span class="dado__val dado__val--preco">{e(fmt_reais(im["preco"]))}</span></div>')
    dados.append('<div class="dado dado--nota"><span class="dado__rot">Atenção</span>'
                 '<span class="dado__val dado__val--nota">Preço e disponibilidade sob confirmação.</span></div>')

    return f"""<article class="imovel" data-tipo="{e(im.get('tipo', ''))}">
  <div class="imovel__capa">
    {f'<div class="imovel__selos">{"".join(selos)}</div>' if selos else ''}
    {capa}
  </div>
  <div class="imovel__corpo">
    <p class="imovel__local">{e(cabeca)}</p>
    <h3 class="imovel__titulo"><a href="{e(im['url'])}">{e(im['titulo'])}</a></h3>
    {f'<p class="imovel__sub">{e(im["subtitulo"])}</p>' if im.get('subtitulo') else ''}
    <div class="imovel__dados">{''.join(dados)}</div>
  </div>
</article>"""


def gerar_home(cfg, pag, imoveis, posts, dados_agro, depoimentos) -> str:
    h = pag.get("home", {})
    zap = montar_url_zap(cfg)

    botoes = f'<a class="btn btn--dourado" href="/imoveis/">{e(h.get("hero_cta", "Ver imÃ³veis"))}</a>'
    if zap:
        botoes += (f'<a class="btn btn--claro" href="{e(zap)}" target="_blank" rel="noopener">'
                   f'{e(h.get("hero_cta_secundario", "Falar com um especialista"))}</a>')
    else:
        botoes += (f'<a class="btn btn--claro" href="/contato/">'
                   f'{e(h.get("hero_cta_secundario", "Falar com um especialista"))}</a>')

    corpo = [hero(cfg, olho=f"{cfg['contato'].get('cidade', '')} Â· {cfg['contato'].get('estado', '')} Â· Matopiba".strip(" Â·"),
                  titulo=h.get("hero_titulo", cfg["marca"]["slogan"]),
                  texto=h.get("hero_texto", ""), botoes=botoes)]

    # pilares
    cards = "".join(
        f'<article class="card"><div class="card__num">{i + 1:02d}</div>'
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
        corpo.append(f"""<section class="secao">
  <div class="env">
    <div class="cabeca-secao">
      <p class="olho">Oportunidades</p>
      <h2>Propriedades em destaque</h2>
      <p class="chamada chamada--larga">PortfÃ³lio verificado. Cada propriedade passou por anÃ¡lise
      documental, ambiental e de mercado antes de ser apresentada.</p>
    </div>
    <div class="grade-imoveis">{''.join(card_imovel(i) for i in destaques[:3])}</div>
    <p style="margin-top:2.5rem"><a class="link-seta" href="/imoveis/">Ver todas as propriedades</a></p>
  </div>
</section>""")

    # indicadores verificados
    indics = [i for i in dados_agro.get("indicadores", []) if not i.get("verificar")]
    if indics:
        blocos = ""
        for i in indics:
            fonte = f'{e(i.get("fonte", ""))} Â· {e(i.get("ano", ""))}'
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
            f'color:var(--azul-800);margin-bottom:1.2rem">â€œ{e(d["texto"])}â€</p>'
            f'<p><strong>{e(d["nome"])}</strong>'
            + (f'<br><span style="font-size:.88rem;color:var(--tinta-suave)">{e(d.get("cargo", ""))}</span>'
               if d.get("cargo") else "")
            + "</p></article>"
            for d in pubs[:3]
        )
        corpo.append(f"""<section class="secao secao--branca">
  <div class="env">
    <div class="cabeca-secao cabeca-secao--centro">
      <p class="olho olho--centro">Quem jÃ¡ negociou com a gente</p>
      <h2>Depoimentos</h2>
    </div>
    <div class="grade grade--3">{cards_dep}</div>
  </div>
</section>""")

    # Ãºltimos posts
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

    corpo.append(cta_faixa(
        cfg,
        "Vamos conversar sobre a sua prÃ³xima propriedade.",
        "Comprar, vender, avaliar ou regularizar. Conte o que vocÃª precisa e um especialista responde.",
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

    return pagina(cfg, titulo=cfg["site"]["titulo_padrao"],
                  descricao=cfg["site"]["descricao_padrao"], url="/",
                  corpo="\n".join(corpo), json_ld=ld,
                  rascunho=any(i.get("_exemplo") or i.get("_rascunho") for i in imoveis))


def card_post(p: dict) -> str:
    return f"""<article class="post-card">
  <p class="post-card__meta"><span class="post-card__cat">{e(p['categoria'])}</span>
  <span>Â·</span><time datetime="{p['data'].isoformat()}">{e(fmt_data(p['data']))}</time></p>
  <h3><a href="{e(p['url'])}">{e(p['titulo'])}</a></h3>
  {f"<p>{e(p['resumo'])}</p>" if p.get('resumo') else ''}
  <a class="link-seta" href="{e(p['url'])}">Ler o artigo</a>
</article>"""


def gerar_sobre(cfg, pag) -> str:
    s = pag.get("sobre", {})
    corpo = [hero(cfg, olho="Sobre nÃ³s", titulo=s.get("titulo", "Sobre a Prime Fazendas"),
                  texto=s.get("chamada", ""), interno=True)]
    corpo.append(f"""<section class="secao">
  <div class="env">
    <div class="prosa">
      <p class="olho">Quem somos</p>
      {paragrafos(s.get('quem_somos'))}
    </div>
  </div>
</section>""")

    corpo.append(f"""<section class="secao secao--clara">
  <div class="env">
    <div class="prosa">
      <p class="olho">{e(s.get('historia_titulo', 'A histÃ³ria'))}</p>
      <h2>De corretor aos 18 ao coraÃ§Ã£o do agro brasileiro</h2>
      {paragrafos(s.get('historia'))}
    </div>
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

    valores = "".join(f"<li>{e(v)}</li>" for v in s.get("valores", []))
    corpo.append(f"""<section class="secao secao--escura">
  <div class="env">
    <div class="grade grade--2" style="align-items:start">
      <div>
        <p class="olho">{e(s.get('missao_titulo', 'Nossa missÃ£o'))}</p>
        <h2>MissÃ£o</h2>
        <p class="chamada">{e(s.get('missao', ''))}</p>
      </div>
      <div>
        <p class="olho">Valores</p>
        <ul class="marcada marcada--check">{valores}</ul>
      </div>
    </div>
  </div>
</section>""")

    corpo.append(cta_faixa(cfg, "Quer conhecer o nosso portfÃ³lio?",
                           "Boa parte das nossas negociaÃ§Ãµes acontece antes do anÃºncio pÃºblico."))

    return pagina(cfg, titulo=s.get("titulo", "Sobre nÃ³s"),
                  descricao=s.get("chamada", cfg["site"]["descricao_padrao"]),
                  url="/sobre/", corpo="\n".join(corpo))


def gerar_servicos(cfg, pag) -> str:
    s = pag.get("servicos", {})
    corpo = [hero(cfg, olho="ServiÃ§os", titulo=s.get("titulo", "Nossos serviÃ§os"),
                  texto=s.get("chamada", ""), interno=True)]

    cards = "".join(
        f'<article class="card"><div class="card__num">{i + 1:02d}</div>'
        f'<h3>{e(x["titulo"])}</h3><p>{e(x["texto"])}</p></article>'
        for i, x in enumerate(s.get("lista", []))
    )
    corpo.append(f"""<section class="secao">
  <div class="env"><div class="grade grade--2">{cards}</div></div>
</section>""")

    corpo.append(cta_faixa(cfg, s.get("cta_titulo", "Cada propriedade Ã© um caso."),
                           s.get("cta_texto", ""), s.get("cta_botao", "Solicitar consultoria")))

    return pagina(cfg, titulo=s.get("titulo", "ServiÃ§os"),
                  descricao=s.get("chamada", ""), url="/servicos/", corpo="\n".join(corpo))


def gerar_investir(cfg, pag, dados_agro) -> str:
    s = pag.get("investir", {})
    corpo = [hero(cfg, olho="Investir no agro", titulo=s.get("titulo", ""),
                  texto=s.get("chamada", ""), interno=True)]

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
    <div class="cabeca-secao"><p class="olho">A tese</p><h2>Por que terra agrÃ­cola</h2></div>
    <div class="grade grade--2">{args}</div>
  </div>
</section>""")

    indics = [i for i in dados_agro.get("indicadores", []) if not i.get("verificar")]
    if indics:
        blocos = ""
        for i in indics:
            fonte = f'{e(i.get("fonte", ""))} Â· {e(i.get("ano", ""))}'
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
    <p class="olho">AtenÃ§Ã£o</p>
    <h2>{e(s.get('fechamento_titulo', ''))}</h2>
    {paragrafos(s.get('fechamento_texto'))}
  </div></div>
</section>""")

    corpo.append(cta_faixa(cfg, "Quer avaliar uma oportunidade?",
                           "Analisamos a propriedade â€” solo, documentaÃ§Ã£o, passivo e preÃ§o â€” antes de vocÃª comprometer capital."))

    return pagina(cfg, titulo=s.get("titulo", "Por que investir no agronegÃ³cio"),
                  descricao=s.get("chamada", ""), url="/investir-no-agro/", corpo="\n".join(corpo))


def gerar_lista_imoveis(cfg, pag, imoveis) -> str:
    s = pag.get("imoveis", {})
    corpo = [hero(cfg, olho="PortfÃ³lio", titulo=s.get("titulo", "ImÃ³veis rurais Ã  venda"),
                  texto=s.get("chamada", ""), interno=True)]
    corpo.append("""<section class="secao secao--compacta">
  <div class="env">
    <div class="painel__alerta" style="margin:0">
      Pre?os, ?rea e disponibilidade s?o confirmados antes da publica??o. Se a propriedade
      estiver reservada ou em negocia??o, ela n?o aparece como dispon?vel.
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
        corpo.append(f"""<section class="secao">
  <div class="env">
    <div class="filtros" role="group" aria-label="Filtrar por tipo">{filtros}</div>
    <p style="color:var(--tinta-suave);font-size:.9rem;margin-bottom:1.75rem">
      <span id="contador-imoveis">{n} {'propriedade' if n == 1 else 'propriedades'}</span>
    </p>
    <div class="grade-imoveis">{''.join(card_imovel(i) for i in imoveis)}</div>
  </div>
</section>""")
    else:
        corpo.append(f"""<section class="secao">
  <div class="env">
    <div class="vazio">
      <h2>{e(s.get('vazio_titulo', 'PortfÃ³lio em atualizaÃ§Ã£o'))}</h2>
      <p>{e(s.get('vazio_texto', ''))}</p>
      <div class="grupo-btn" style="justify-content:center;margin-top:2rem">
        <a class="btn btn--principal" href="/contato/">Falar com um especialista</a>
      </div>
    </div>
  </div>
</section>""")

    corpo.append(cta_faixa(cfg, "Procura algo especÃ­fico?",
                           "Diga regiÃ£o, tamanho, aptidÃ£o e faixa de investimento. Boa parte do que negociamos nÃ£o chega a ser anunciado."))

    return pagina(cfg, titulo=s.get("titulo", "ImÃ³veis rurais Ã  venda"),
                  descricao=s.get("chamada", ""), url="/imoveis/",
                  corpo="\n".join(corpo),
                  rascunho=any(i.get("_exemplo") or i.get("_rascunho") for i in imoveis))


def gerar_ficha_imovel(cfg, im) -> str:
    local = ", ".join(x for x in [im.get("municipio"), im.get("estado")] if x)
    olho = " Â· ".join(x for x in [local, TIPOS.get(im.get("tipo", ""), ""), im.get("regiao", "")] if x)

    corpo = [f'<section class="secao secao--compacta"><div class="env">'
             + migalhas([("InÃ­cio", "/"), ("ImÃ³veis", "/imoveis/"), (im["titulo"], "")])
             + f'<p class="olho">{e(olho)}</p><h1>{e(im["titulo"])}</h1>'
             + (f'<p class="chamada chamada--larga">{e(im["subtitulo"])}</p>' if im.get("subtitulo") else "")
             + "</div></section>"]

    # galeria
    if im["fotos_url"]:
        fotos = "".join(
            f'<a class="galeria__link" href="{e(u)}" target="_blank" rel="noopener noreferrer" '
            f'title="Abrir foto {n + 1} em nova aba">'
            f'<img src="{e(u)}" alt="{e(im["titulo"])} â€” foto {n + 1}" loading="lazy">'
            f'</a>'
            for n, u in enumerate(im["fotos_url"])
        )
        galeria = f'<div class="galeria">{fotos}</div>'
    if im.get("descricao"):
        blocos.append(f'<div class="bloco-ficha"><h3>A propriedade</h3>'
                      f'<div class="prosa">{paragrafos(im["descricao"])}</div></div>')

    for titulo, chave in [("CaracterÃ­sticas", "caracteristicas"),
                          ("Infraestrutura", "infraestrutura"),
                          ("DocumentaÃ§Ã£o", "documentacao")]:
        itens = im.get(chave) or []
        if itens:
            marcador = "marcada marcada--check" if chave == "documentacao" else "marcada"
            blocos.append(f'<div class="bloco-ficha"><h3>{e(titulo)}</h3>'
                          f'<ul class="{marcador}">'
                          + "".join(f"<li>{e(i)}</li>" for i in itens) + "</ul></div>")

    if preenchido(im.get("video_youtube")):
        vid = e(im["video_youtube"])
        blocos.append(f'<div class="bloco-ficha"><h3>VÃ­deo</h3><div class="mapa">'
                      f'<iframe src="https://www.youtube-nocookie.com/embed/{vid}" '
                      f'title="VÃ­deo da propriedade" loading="lazy" allowfullscreen></iframe></div></div>')

    if preenchido(im.get("mapa_embed")):
        blocos.append(f'<div class="bloco-ficha"><h3>LocalizaÃ§Ã£o</h3><div class="mapa">'
                      f'<iframe src="{e(im["mapa_embed"])}" title="Mapa da propriedade" '
                      f'loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe></div></div>')

    # painel lateral
    if im.get("preco_sob_consulta") or not im.get("preco"):
        preco_html = '<p class="painel__preco">Sob consulta</p>'
        nota = '<p class="painel__preco-nota">Valor informado no primeiro contato.</p>'
    else:
        preco_html = f'<p class="painel__preco">{e(fmt_reais(im["preco"]))}</p>'
        nota = ""
        if im.get("preco_ha"):
            nota = (f'<p class="painel__preco-nota">â‰ˆ R$ {fmt_num(round(im["preco_ha"]))} por hectare</p>')
    nota += '<p class="painel__alerta">Preço, área e disponibilidade são confirmados antes de qualquer proposta.</p>'

    linhas = []
    if im.get("area_total_ha"):
        linhas.append(("Ãrea total", f'{fmt_num(im["area_total_ha"])} ha'))
    if im.get("area_aberta_ha"):
        linhas.append(("Ãrea aberta", f'{fmt_num(im["area_aberta_ha"])} ha'))
    if im.get("area_reserva_ha"):
        linhas.append(("Reserva / APP", f'{fmt_num(im["area_reserva_ha"])} ha'))
    if local:
        linhas.append(("LocalizaÃ§Ã£o", local))
    if im.get("regiao"):
        linhas.append(("RegiÃ£o", im["regiao"]))
    if im.get("tipo"):
        linhas.append(("AptidÃ£o", TIPOS.get(im["tipo"], im["tipo"])))
    rotulo_status, _ = STATUS.get(im.get("status", "disponivel"), STATUS["disponivel"])
    linhas.append(("SituaÃ§Ã£o", rotulo_status))

    linhas_html = "".join(
        f'<li><span class="rot">{e(r)}</span><span class="val">{e(v)}</span></li>'
        for r, v in linhas
    )

    msg = f"OlÃ¡! Tenho interesse na {im['titulo']} ({local}). Vi no site da Prime Fazendas."
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
  <p class="form__nota" style="margin-top:1.1rem">Dados sujeitos a confirmaÃ§Ã£o em due diligence.</p>
</aside>"""

    corpo.append(f'<section class="secao secao--compacta"><div class="env">'
                 f'<div class="ficha"><div>{"".join(blocos)}</div>{painel}</div></div></section>')

    corpo.append(cta_faixa(cfg, "Quer ver outras opÃ§Ãµes?",
                           "Temos propriedades que nÃ£o estÃ£o publicadas no site.",
                           "Falar com um especialista"))

    desc = im.get("subtitulo") or f"{im['titulo']} â€” {local}."
    ld = json.dumps({
        "@context": "https://schema.org",
        "@type": "Product",
        "name": im["titulo"],
        "description": desc,
        "category": "ImÃ³vel rural",
        **({"offers": {
            "@type": "Offer",
            "price": im["preco"],
            "priceCurrency": "BRL",
            "availability": ("https://schema.org/InStock"
                             if im.get("status") == "disponivel"
                             else "https://schema.org/OutOfStock"),
        }} if im.get("preco") and not im.get("preco_sob_consulta") else {}),
    }, ensure_ascii=False)

    return pagina(cfg, titulo=im["titulo"], descricao=desc, url=im["url"],
                  corpo="\n".join(corpo), og_tipo="article", json_ld=ld,
                  rascunho=bool(im.get("_exemplo") or im.get("_rascunho")))


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
        aviso("comunidade: 'grupo_whatsapp' e 'canal_whatsapp' estÃ£o vazios â€” o botÃ£o aponta para /contato/ atÃ© vocÃª colar um link vÃ¡lido.")

    corpo = [hero(cfg, olho="Comunidade", titulo=s.get("titulo", com.get("nome", "Comunidade")),
                  texto=s.get("chamada", ""), botoes=botoes, interno=True)]

    corpo.append(f'<section class="secao"><div class="env"><div class="prosa">'
                 f'{paragrafos(s.get("intro"))}</div></div></section>')

    bens = "".join(
        f'<article class="card"><h3>{e(b["titulo"])}</h3><p>{e(b["texto"])}</p></article>'
        for b in s.get("beneficios", [])
    )
    if bens:
        corpo.append(f"""<section class="secao secao--clara">
  <div class="env">
    <div class="cabeca-secao"><p class="olho">O que vocÃª recebe</p>
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


def gerar_blog(cfg, pag, posts) -> str:
    s = pag.get("blog", {})
    corpo = [hero(cfg, olho="Blog", titulo=s.get("titulo", "Blog e insights"),
                  texto=s.get("chamada", ""), interno=True)]

    if posts:
        corpo.append(f'<section class="secao"><div class="env">'
                     f'<div class="grade-posts">{"".join(card_post(p) for p in posts)}</div>'
                     f"</div></section>")
    else:
        corpo.append(f'<section class="secao"><div class="env"><div class="vazio">'
                     f'<h2>{e(s.get("vazio_titulo", "Em breve"))}</h2>'
                     f'<p>{e(s.get("vazio_texto", ""))}</p></div></div></section>')

    return pagina(cfg, titulo=s.get("titulo", "Blog"), descricao=s.get("chamada", ""),
                  url="/blog/", corpo="\n".join(corpo))


def gerar_post(cfg, p, outros) -> str:
    corpo = [f"""<section class="secao secao--compacta">
  <div class="env">
    <div class="artigo">
      {migalhas([("InÃ­cio", "/"), ("Blog", "/blog/"), (p['titulo'], "")])}
      <p class="artigo__meta"><span class="post-card__cat">{e(p['categoria'])}</span>
      <span>Â·</span><time datetime="{p['data'].isoformat()}">{e(fmt_data(p['data']))}</time>
      <span>Â·</span><span>{e(p['autor'])}</span></p>
      <h1>{e(p['titulo'])}</h1>
      {f'<p class="chamada chamada--larga">{e(p["resumo"])}</p>' if p.get('resumo') else ''}
    </div>
  </div>
</section>
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

    corpo.append(cta_faixa(cfg, "Tem uma propriedade ou uma dÃºvida?",
                           "Fale com quem negocia terra no Tocantins todos os dias."))

    ld = json.dumps({
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": p["titulo"],
        "description": p.get("resumo", ""),
        "datePublished": p["data"].isoformat(),
        "author": {"@type": "Organization", "name": p["autor"]},
        "publisher": {"@type": "Organization", "name": cfg["marca"]["nome"]},
        "mainEntityOfPage": cfg["site"]["dominio"].rstrip("/") + p["url"],
    }, ensure_ascii=False)

    return pagina(cfg, titulo=p["titulo"], descricao=p.get("resumo", ""), url=p["url"],
                  corpo="\n".join(corpo), og_tipo="article", json_ld=ld)


def gerar_contato(cfg, pag) -> str:
    s = pag.get("contato", {})
    c = cfg["contato"]

    corpo = [hero(cfg, olho="Contato", titulo=s.get("titulo", "Contato e consultoria"),
                  texto=s.get("chamada", ""), interno=True)]

    numero_zap = re.sub(r"\D", "", str(c.get("whatsapp_numero_internacional") or "")) \
        if preenchido(c.get("whatsapp_numero_internacional")) else ""

    form = f"""<form class="form" data-modo="whatsapp" data-whatsapp="{e(numero_zap)}">
  <div class="campo--duplo">
    <div class="campo">
      <label for="nome">Nome <span class="req">*</span></label>
      <input type="text" id="nome" name="nome" required autocomplete="name">
    </div>
    <div class="campo">
      <label for="telefone">Telefone / WhatsApp <span class="req">*</span></label>
      <input type="tel" id="telefone" name="telefone" required autocomplete="tel">
    </div>
  </div>
  <div class="campo">
    <label for="email">E-mail</label>
    <input type="email" id="email" name="email" autocomplete="email">
  </div>
  <div class="campo--duplo">
    <div class="campo">
      <label for="interesse">O que vocÃª busca</label>
      <select id="interesse" name="interesse">
        <option>Comprar uma propriedade</option>
        <option>Vender minha propriedade</option>
        <option>Avaliar uma propriedade</option>
        <option>RegularizaÃ§Ã£o fundiÃ¡ria ou ambiental</option>
        <option>Investir no agro</option>
        <option>Outro assunto</option>
      </select>
    </div>
    <div class="campo">
      <label for="regiao">RegiÃ£o de interesse</label>
      <input type="text" id="regiao" name="regiao" placeholder="Ex: Palmas, Matopiba, Vale do Araguaia">
    </div>
  </div>
  <div class="campo">
    <label for="investimento">Faixa de investimento</label>
    <select id="investimento" name="investimento">
      <option>Prefiro nÃ£o informar</option>
      <option>AtÃ© R$ 5 milhÃµes</option>
      <option>R$ 5 a 20 milhÃµes</option>
      <option>R$ 20 a 50 milhÃµes</option>
      <option>Acima de R$ 50 milhÃµes</option>
    </select>
  </div>
  <div class="campo">
    <label for="mensagem">Mensagem</label>
    <textarea id="mensagem" name="mensagem" placeholder="Conte o que vocÃª procura: tamanho, aptidÃ£o, regiÃ£o, prazo."></textarea>
  </div>
  <div class="grupo-btn">
    <button class="btn btn--principal" type="submit">Enviar pelo WhatsApp</button>
  </div>
  <p class="form__nota">{e(s.get('form_nota', ''))}</p>
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
        itens.append(("EndereÃ§o", e(c["endereco"])))
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
    ) or '<div class="contato-item"><p class="contato-item__val">Dados de contato em atualizaÃ§Ã£o.</p></div>'

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

    return pagina(cfg, titulo=s.get("titulo", "Contato"), descricao=s.get("chamada", ""),
                  url="/contato/", corpo="\n".join(corpo))


def gerar_404(cfg) -> str:
    corpo = [f"""<section class="secao">
  <div class="env centro" style="padding-block:clamp(3rem,10vw,6rem)">
    <p class="olho olho--centro">Erro 404</p>
    <h1>Esta pÃ¡gina nÃ£o existe</h1>
    <p class="chamada chamada--larga" style="margin-inline:auto">
      O endereÃ§o pode ter mudado ou a propriedade que vocÃª procurava jÃ¡ foi negociada.
    </p>
    <div class="grupo-btn" style="justify-content:center;margin-top:2.25rem">
      <a class="btn btn--principal" href="/">Ir para o inÃ­cio</a>
      <a class="btn btn--vazado" href="/imoveis/">Ver imÃ³veis</a>
    </div>
  </div>
</section>"""]
    return pagina(cfg, titulo="PÃ¡gina nÃ£o encontrada", descricao="PÃ¡gina nÃ£o encontrada.",
                  url="/404.html", corpo="\n".join(corpo))


FAVICON = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">'
    '<rect width="128" height="128" rx="20" fill="#0C1E33"/>'
    + svg_marca(classe="", tam=128, ident="fav")
    .replace('<svg class="" width="128" height="128" ', "<svg ")
    .replace('viewBox="0 0 128 128">', 'viewBox="0 0 128 128" x="0" y="0" width="128" height="128">')
    .replace('fill="currentColor"', 'fill="#C9A44C"')
    + "</svg>"
)

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


HTACCESS = """# Prime Fazendas â€” configuraÃ§Ã£o de servidor (Apache / site estatÃ­co)

# HTTPS obrigatÃ³rio
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

# CompressÃ£o
<IfModule mod_deflate.c>
  AddOutputFilterByType DEFLATE text/html text/css text/plain text/xml application/javascript application/json image/svg+xml
</IfModule>

# Cache dos estÃ¡ticos
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

# SeguranÃ§a
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

def escrever(caminho_rel: str, conteudo: str) -> None:
    destino = SAIDA / caminho_rel
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(conteudo, encoding="utf-8", newline="\n")


def auditar(cfg: dict, imoveis: list, posts: list, dados_agro: dict, depoimentos: dict) -> None:
    """Checagens que o fluxo de publicacao usa para decidir se pode seguir."""
    for grupo in ("contato", "redes", "comunidade"):
        for chave, valor in (cfg.get(grupo) or {}).items():
            if chave.startswith("_"):
                continue
            if str(valor).strip() == PENDENTE:
                aviso(f"config.json â†’ {grupo}.{chave} ainda estÃ¡ em {PENDENTE}.")

    if MOSTRAR_RASCUNHOS:
        n_r = sum(1 for i in imoveis if i.get("_rascunho")) + sum(1 for p in posts if p.get("_rascunho"))
        aviso(f"MODO RASCUNHO (--demo): {n_r} item(ns) nao publicado(s) estao aparecendo. "
              f"Isso e so para voce ver o layout â€” o fluxo de publicacao ignora este modo.")

    # Dado de teste que escapa para o ar e pior do que campo vazio: telefone que
    # ninguem atende perde lead, e CRECI falso e numero de registro regulado â€”
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
        bloqueio("imÃ³veis de EXEMPLO publicados: " + ", ".join(exemplos)
                 + ". Troque pelos dados reais ou marque publicado=false antes de subir.")

    suspeita_preco = []
    for i in imoveis:
        if i.get("preco_sob_consulta") or not i.get("preco"):
            continue
        preco_ha = i.get("preco_ha") or 0
        if preco_ha and preco_ha < 1000:
            suspeita_preco.append(
                f"{i.get('arquivo', i.get('slug', 'im?vel'))} ? {fmt_num(round(preco_ha))}/ha"
            )
    if suspeita_preco:
        aviso(
            "pre?o por hectare muito abaixo do esperado em: "
            + "; ".join(suspeita_preco)
            + ". Confirme ?rea, moeda e disponibilidade antes de publicar."
        )

    nao_verif = [i.get("rotulo", "?") for i in dados_agro.get("indicadores", []) if i.get("verificar")]
    if nao_verif:
        aviso(f"{len(nao_verif)} indicador(es) em dados-agro.json com verificar=true â€” "
              f"nÃ£o estÃ£o sendo exibidos no site atÃ© vocÃª confirmar a fonte.")

    if not imoveis:
        aviso("nenhum imÃ³vel publicado â€” a pÃ¡gina /imoveis/ vai mostrar o estado 'em atualizaÃ§Ã£o'.")
    if not posts:
        aviso("nenhum post publicado â€” /blog/ vai mostrar 'em breve'.")

    if not any(d.get("publicado") for d in depoimentos.get("depoimentos", [])):
        aviso("nenhum depoimento publicado â€” a seÃ§Ã£o de prova social nÃ£o aparece na home.")


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
    posts = carregar_posts()

    auditar(cfg, imoveis, posts, dados_agro, depoimentos)

    if apenas_auditar:
        relatar(0)
        return 1 if bloqueios else 0

    # limpa a saÃ­da, preservando o .git se alguÃ©m apontar para lÃ¡ por engano
    if SAIDA.exists():
        for item in SAIDA.iterdir():
            if item.name == ".git":
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
    SAIDA.mkdir(parents=True, exist_ok=True)

    # estÃ¡ticos
    shutil.copytree(TEMA / "assets", SAIDA / "assets", dirs_exist_ok=True)
    escrever("assets/favicon.svg", FAVICON)

    midia = CONTEUDO / "midia"
    if midia.exists():
        shutil.copytree(midia, SAIDA / "midia", dirs_exist_ok=True)

    # pÃ¡ginas
    escrever("index.html", gerar_home(cfg, pag, imoveis, posts, dados_agro, depoimentos))
    escrever("sobre/index.html", gerar_sobre(cfg, pag))
    escrever("servicos/index.html", gerar_servicos(cfg, pag))
    escrever("investir-no-agro/index.html", gerar_investir(cfg, pag, dados_agro))
    escrever("imoveis/index.html", gerar_lista_imoveis(cfg, pag, imoveis))
    escrever("comunidade/index.html", gerar_comunidade(cfg, pag))
    escrever("blog/index.html", gerar_blog(cfg, pag, posts))
    escrever("contato/index.html", gerar_contato(cfg, pag))
    escrever("404.html", gerar_404(cfg))

    for im in imoveis:
        escrever(f"imoveis/{im['slug']}/index.html", gerar_ficha_imovel(cfg, im))
    for p in posts:
        escrever(f"blog/{p['slug']}/index.html", gerar_post(cfg, p, posts))

    # sitemap + robots + htaccess
    dominio = cfg["site"]["dominio"].rstrip("/")
    urls = ["/", "/sobre/", "/servicos/", "/investir-no-agro/", "/imoveis/",
            "/comunidade/", "/blog/", "/contato/"]
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
        escrever("robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {dominio}/sitemap.xml\n")

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
    print("  PRIME FAZENDAS â€” build")
    print("=" * 68)

    if n_html:
        print(f"  pÃ¡ginas geradas .... {n_html}")
        print(f"  imÃ³veis ............ {len(imoveis or [])}")
        print(f"  artigos ............ {len(posts or [])}")
        try:
            destino = SAIDA.relative_to(RAIZ)
            destino_txt = f"{destino.as_posix()}/"
        except Exception:
            destino_txt = str(SAIDA)
        print(f"  saÃ­da .............. {destino_txt}")

    if avisos:
        print()
        print(f"  AVISOS ({len(avisos)}) â€” o site funciona, mas confira:")
        for a in avisos:
            print(f"    Â· {a}")

    if bloqueios:
        print()
        print(f"  BLOQUEIOS ({len(bloqueios)}) â€” resolva antes de publicar:")
        for b in bloqueios:
            print(f"    ! {b}")
    elif n_html:
        print()
        print("  Sem bloqueios. Pronto para publicar.")

    print("=" * 68)
    print()


if __name__ == "__main__":
    sys.exit(main())
