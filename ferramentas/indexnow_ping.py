#!/usr/bin/env python3
"""Dispara o protocolo IndexNow (indexnow.org) para todas as URLs do sitemap.xml.

Bing, Yandex e outros mecanismos que participam do IndexNow recebem um aviso
instantâneo de que essas páginas mudaram, em vez de esperar o próximo rastreio
agendado. A chave de posse já é publicada em https://<dominio>/<chave>.txt pelo
próprio build.py — este script só avisa o endpoint depois que o deploy sobe.

Uso:
    python3 ferramentas/indexnow_ping.py

Lê a chave em conteudo/config.json (seo.indexnow_key) e a lista de URLs em
site/sitemap.xml. Não falha o build/deploy se a chamada de rede não funcionar
(o CI não deve quebrar por causa de um serviço de terceiro fora do ar) — só
avisa no log.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ENDPOINT = "https://api.indexnow.org/indexnow"


def carregar_chave() -> str | None:
    caminho = RAIZ / "conteudo" / "config.json"
    try:
        cfg = json.loads(caminho.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    return cfg.get("seo", {}).get("indexnow_key")


def carregar_urls() -> list[str]:
    caminho = RAIZ / "site" / "sitemap.xml"
    xml = caminho.read_text(encoding="utf-8")
    return re.findall(r"<loc>(.*?)</loc>", xml)


def dominio_de(urls: list[str]) -> str | None:
    if not urls:
        return None
    m = re.match(r"https?://([^/]+)", urls[0])
    return m.group(1) if m else None


def enviar(chave: str, host: str, urls: list[str]) -> None:
    # IndexNow aceita até 10.000 URLs por chamada — o site tem bem menos que isso,
    # mas o corte fica aqui por segurança caso o site cresça muito.
    lote = urls[:10_000]
    payload = json.dumps({
        "host": host,
        "key": chave,
        "keyLocation": f"https://{host}/{chave}.txt",
        "urlList": lote,
    }).encode("utf-8")

    req = urllib.request.Request(
        ENDPOINT, data=payload, method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            print(f"IndexNow: {resp.status} — {len(lote)} URLs enviadas para {host}")
    except urllib.error.HTTPError as exc:
        # 200/202 = aceito; outros códigos do protocolo estão documentados em
        # https://www.indexnow.org/documentation — nenhum deles deve derrubar o CI.
        print(f"IndexNow: aviso HTTP {exc.code} ({exc.reason}) — não bloqueante", file=sys.stderr)
    except urllib.error.URLError as exc:
        print(f"IndexNow: não foi possível contatar o endpoint ({exc.reason}) — não bloqueante", file=sys.stderr)


def main() -> int:
    chave = carregar_chave()
    if not chave:
        print("IndexNow: nenhuma seo.indexnow_key em conteudo/config.json — nada a fazer.")
        return 0

    urls = carregar_urls()
    if not urls:
        print("IndexNow: site/sitemap.xml vazio ou não encontrado — rode build.py antes.", file=sys.stderr)
        return 0

    host = dominio_de(urls)
    if not host:
        print("IndexNow: não deu para extrair o domínio das URLs do sitemap.", file=sys.stderr)
        return 0

    enviar(chave, host, urls)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
