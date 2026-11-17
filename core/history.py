# -*- coding: utf-8 -*-
"""Histórico de downloads por plataforma, com migração do formato antigo."""

import json
from pathlib import Path

HISTORY_FILE = "download_history.json"

_history = None


def _default() -> dict:
    return {"twitter": set(), "pixiv": set(), "pinterest": set()}


def load_history() -> dict:
    """Carrega o histórico (ou migra o formato antigo de lista simples)."""
    global _history
    if _history is not None:
        return _history

    if Path(HISTORY_FILE).exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                # Formato antigo: lista simples de IDs de tweets.
                _history = {"twitter": set(data), "pixiv": set(), "pinterest": set()}
                save_history()
            elif isinstance(data, dict):
                _history = {k: set(v) for k, v in data.items()}
            else:
                _history = _default()
        except Exception:
            _history = _default()
    else:
        _history = _default()

    return _history


def save_history() -> None:
    """Persiste o histórico em disco."""
    if _history is None:
        return
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(
                {k: sorted(v) for k, v in _history.items()},
                f,
                indent=4,
                ensure_ascii=False,
            )
    except Exception as e:
        print(f"⚠️ Erro ao salvar histórico: {e}")


def is_downloaded(platform: str, source_id: str) -> bool:
    return source_id in load_history().get(platform, set())


def mark_downloaded(platform: str, source_id: str) -> None:
    load_history().setdefault(platform, set()).add(source_id)
    save_history()
