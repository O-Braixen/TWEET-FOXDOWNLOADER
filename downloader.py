#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
🦊 FOXDOWNLOADER 🦊
Utilitário assíncrono multi-plataforma para baixar mídias (imagens, vídeos e GIFs)
de Twitter/X, Pixiv e Pinterest — usando apenas cookies de sessão.
"""

import asyncio
import io
import sys

from core.config import load_config
from core.download import run_download
from core.history import load_history
from platforms import ADAPTERS

# Configurar saída padrão do terminal para UTF-8 no Windows
if sys.platform.startswith("win"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def pick(prompt: str, options: list):
    """Lê uma escolha válida (1..N). Retorna o item escolhido ou None (0/vazio)."""
    while True:
        try:
            raw = input(prompt).strip()
        except EOFError:
            return None
        if raw in ("0", ""):
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        print(f"❌ Opção inválida. Digite um número de 0 a {len(options)}.")


async def main():
    print("=" * 65)
    print("      🦊 FOXDOWNLOADER - MULTI-DOWNLOADER DE MÍDIAS 🦊      ")
    print("=" * 65)

    config = load_config()
    history = load_history()

    print("\n--- PLATAFORMAS SUPORTADAS ---")
    for idx, adapter_cls in enumerate(ADAPTERS, start=1):
        print(f"{idx}. {adapter_cls.display_name}")
    print("0. 🚪 Sair do programa")
    print("-" * 65)

    adapter_cls = pick("👉 Escolha uma plataforma: ", ADAPTERS)
    if adapter_cls is None:
        print("Até logo!")
        return

    adapter = adapter_cls(config, history)

    try:
        if not await adapter.authenticate():
            print("\n❌ Não foi possível autenticar. Verifique os arquivos de cookies e tente novamente.")
            return

        try:
            summary = await adapter.summary()
        except Exception as e:
            summary = [f"⚠️ Não foi possível montar o resumo ({type(e).__name__})."]
        if summary:
            print("\n--- 📊 RESUMO DA CONTA ---")
            for line in summary:
                print(line)
            print("-" * 65)

        all_actions = adapter.actions() + await adapter.extra_actions()

        print(f"\n--- AÇÕES ({adapter.display_name}) ---")
        for idx, action in enumerate(all_actions, start=1):
            print(f"{idx}. {action.label}")
        print("0. 🔙 Voltar")
        print("-" * 65)

        action = pick("👉 Escolha uma ação: ", all_actions)
        if action is None:
            print("Até logo!")
            return

        item_iter = action.fetch()
        await run_download(adapter.name, action.folder, item_iter)
    finally:
        await adapter.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n🛑 Processo interrompido pelo usuário. Até logo!")
        sys.exit(0)
