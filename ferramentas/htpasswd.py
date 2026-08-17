#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera o hash de senha no formato APR1-MD5, o mesmo que o utilitario `htpasswd`
do Apache produz por padrao.

Por que APR1 e nao bcrypt: o modulo `crypt` saiu da biblioteca padrao no
Python 3.13 e bcrypt exigiria dependencia externa. APR1 e implementavel com
hashlib puro e e aceito por qualquer Apache.

Uso como biblioteca:
    from htpasswd import gerar_hash
    gerar_hash("minha-senha")

Uso na linha de comando:
    python ferramentas/htpasswd.py minha-senha
"""

import hashlib
import secrets
import sys

ALFABETO = "./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def _para_base64_apr(entrada: bytes) -> str:
    """Codificacao base64 propria do APR1 (ordem de bits diferente da padrao)."""
    ordem = [(0, 6, 12), (1, 7, 13), (2, 8, 14), (3, 9, 15), (4, 10, 5)]
    saida = []
    for a, b, c in ordem:
        v = (entrada[a] << 16) | (entrada[b] << 8) | entrada[c]
        for _ in range(4):
            saida.append(ALFABETO[v & 0x3F])
            v >>= 6
    v = entrada[11]
    saida.append(ALFABETO[v & 0x3F])
    saida.append(ALFABETO[(v >> 6) & 0x3F])
    return "".join(saida)


def gerar_hash(senha: str, sal: str | None = None) -> str:
    """Devolve o hash no formato $apr1$<sal>$<resumo>."""
    if sal is None:
        sal = "".join(secrets.choice(ALFABETO) for _ in range(8))
    sal = sal[:8]

    senha_b = senha.encode("utf-8")
    sal_b = sal.encode("utf-8")

    # resumo auxiliar, usado para semear o resultado
    aux = hashlib.md5(senha_b + sal_b + senha_b).digest()

    ctx = hashlib.md5(senha_b + b"$apr1$" + sal_b)
    tam = len(senha_b)
    while tam > 0:
        ctx.update(aux[: min(tam, 16)])
        tam -= 16

    # o bit 1 de cada posicao decide entre um byte nulo e o primeiro da senha
    i = len(senha_b)
    while i:
        ctx.update(b"\0" if i & 1 else senha_b[:1])
        i >>= 1

    resumo = ctx.digest()

    # 1000 voltas de reforco — e o que torna a quebra por forca bruta cara
    for i in range(1000):
        c = hashlib.md5()
        c.update(senha_b if i & 1 else resumo)
        if i % 3:
            c.update(sal_b)
        if i % 7:
            c.update(senha_b)
        c.update(resumo if i & 1 else senha_b)
        resumo = c.digest()

    return f"$apr1${sal}${_para_base64_apr(resumo)}"


def verificar(senha: str, hash_completo: str) -> bool:
    partes = hash_completo.split("$")
    if len(partes) != 4 or partes[1] != "apr1":
        return False
    return secrets.compare_digest(gerar_hash(senha, partes[2]), hash_completo)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("uso: python ferramentas/htpasswd.py <senha>")
        sys.exit(1)
    print(gerar_hash(sys.argv[1]))
