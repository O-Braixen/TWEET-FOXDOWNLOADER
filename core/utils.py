# -*- coding: utf-8 -*-
"""Funções auxiliares compartilhadas."""

import datetime
from typing import Optional

import httpx


async def download_url_to(client, url: str, dest, referer: Optional[str] = None):
    """Baixa uma URL direta para `dest`.

    Retorna uma tupla (sucesso: bool, motivo_do_erro: str | None).
    """
    headers = {"Referer": referer} if referer else {}
    try:
        resp = await client.get(url, headers=headers)
    except httpx.TimeoutException:
        return False, "tempo esgotado (timeout)"
    except httpx.HTTPError as e:
        return False, f"falha de rede ({type(e).__name__})"

    if resp.status_code == 200:
        dest.write_bytes(resp.content)
        return True, None
    if resp.status_code in (401, 403):
        return False, f"HTTP {resp.status_code} (acesso negado — cookies podem ter expirado)"
    if resp.status_code == 404:
        return False, "HTTP 404 (mídia não encontrada/removida)"
    if resp.status_code == 429:
        return False, "HTTP 429 (limite de requisições — aguarde e tente de novo)"
    return False, f"HTTP {resp.status_code}"


def normalize_date(value) -> Optional[str]:
    """Converte datetime/string/data em 'YYYY-MM-DD' quando possível."""
    if not value:
        return None

    if hasattr(value, "strftime"):
        try:
            return value.strftime("%Y-%m-%d")
        except Exception:
            return None

    if isinstance(value, str):
        text = value.strip()
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.datetime.strptime(text[:19], fmt).strftime("%Y-%m-%d")
            except Exception:
                continue
        if len(text) >= 10:
            return text[:10].replace("/", "-")

    return None


def sanitize_filename(name: str) -> str:
    """Remove caracteres inválidos de nomes de arquivo."""
    return "".join(c for c in name if c.isalnum() or c in "-_.")
