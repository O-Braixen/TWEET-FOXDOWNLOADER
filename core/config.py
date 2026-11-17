# -*- coding: utf-8 -*-
"""Carregamento de config.json com valores padrão."""

import copy
import json
from pathlib import Path

CONFIG_FILE = "config.json"

DEFAULTS = {
    "twitter": {"cookies_file": "cookies.json"},
    "pixiv": {"cookies_file": "pixiv_cookies.json"},
    "pinterest": {"cookies_file": "pinterest_cookies.json", "username": ""},
}


def _write_defaults() -> None:
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULTS, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️ Erro ao criar {CONFIG_FILE}: {e}")


def load_config() -> dict:
    """Carrega a configuração, criando o arquivo padrão se necessário."""
    if not Path(CONFIG_FILE).exists():
        _write_defaults()
        print(
            f"ℹ️ Arquivo '{CONFIG_FILE}' criado. Preencha os campos necessários "
            f"(ex.: 'username' do Pinterest e os caminhos dos arquivos de cookies)."
        )
        return copy.deepcopy(DEFAULTS)

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"⚠️ Erro ao ler {CONFIG_FILE}: {e}. Usando padrões.")
        return copy.deepcopy(DEFAULTS)

    merged = copy.deepcopy(DEFAULTS)
    for key, value in data.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key].update(value)
        else:
            merged[key] = value
    return merged
