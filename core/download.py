# -*- coding: utf-8 -*-
"""Motor concorrente de download compartilhado entre plataformas."""

import asyncio
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import httpx
from tqdm import tqdm

from .history import mark_downloaded
from .utils import download_url_to

DOWNLOAD_DELAY = 1.5
BATCH_SIZE = 20


@dataclass
class ItemResult:
    """Resultado do processamento de uma única MediaItem."""

    new_count: int = 0
    ok: bool = False
    media_type: str = "photo"
    size_bytes: int = 0
    error: str | None = None


async def download_media_item(item, platform: str, client, images_dir: Path, videos_dir: Path) -> ItemResult:
    """Baixa uma única MediaItem e retorna um ItemResult detalhado."""
    result = ItemResult(media_type=item.media_type)

    prefix = f"{item.date}_" if item.date else ""
    base_name = f"{prefix}{platform}_{item.source_id}_{item.index}"

    if item.media_type == "photo":
        dest = images_dir / f"{base_name}.jpg"
    else:
        ext = "gif" if item.media_type == "gif" else "mp4"
        dest = videos_dir / f"{base_name}.{ext}"

    if dest.exists():
        result.ok = True
        return result

    ok = False
    error = None

    download_fn = item.extra.get("download_fn")
    if callable(download_fn):
        try:
            ok = await download_fn(dest)
            if not ok:
                error = "a plataforma não retornou o arquivo"
        except Exception as e:
            error = _short_error(e)

    if not ok:
        downloadable = item.extra.get("downloadable")
        if downloadable is not None:
            try:
                await downloadable.download(str(dest))
                ok = dest.exists()
                if not ok:
                    error = "arquivo não foi gerado"
            except Exception as e:
                error = _short_error(e)

    if not ok and item.url:
        ok, net_error = await download_url_to(client, item.url, dest, item.referer)
        if not ok:
            error = net_error

    result.ok = ok
    if ok:
        result.new_count = 1
        try:
            result.size_bytes = dest.stat().st_size
        except OSError:
            result.size_bytes = 0
    else:
        result.error = error or "erro desconhecido"

    return result


def _short_error(exc: Exception) -> str:
    text = str(exc).strip().replace("\n", " ")
    if len(text) > 120:
        text = text[:117] + "..."
    return f"{type(exc).__name__}: {text}" if text else type(exc).__name__


async def run_download(platform: str, action_folder: str, item_iter) -> dict:
    """Consome um iterador assíncrono de MediaItem e baixa tudo em paralelo."""
    base_dir = Path("downloads") / platform / action_folder
    images_dir = base_dir / "images"
    videos_dir = base_dir / "videos"
    images_dir.mkdir(parents=True, exist_ok=True)
    videos_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 65)
    print(f"📂 Imagens: {images_dir.resolve()}")
    print(f"📂 Vídeos:  {videos_dir.resolve()}")
    print("=" * 65)

    stats = {
        "processed": 0,
        "downloaded": 0,
        "images": 0,
        "videos": 0,
        "gifs": 0,
        "bytes": 0,
    }
    errors: Counter = Counter()
    started = time.monotonic()

    pbar = tqdm(desc="Processando mídias", unit="mídia")
    interrupted = None

    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        batch = []
        try:
            async for item in item_iter:
                stats["processed"] += 1
                batch.append(item)

                if len(batch) >= BATCH_SIZE:
                    await _process_batch(
                        batch, platform, client, images_dir, videos_dir, stats, errors
                    )
                    pbar.update(len(batch))
                    batch = []
                    await asyncio.sleep(DOWNLOAD_DELAY)

            if batch:
                await _process_batch(
                    batch, platform, client, images_dir, videos_dir, stats, errors
                )
                pbar.update(len(batch))
        except Exception as e:
            interrupted = _short_error(e)

    pbar.close()

    elapsed = time.monotonic() - started
    _print_summary(stats, errors, elapsed, interrupted)
    return stats


async def _process_batch(batch, platform, client, images_dir, videos_dir, stats, errors) -> None:
    tasks = [
        download_media_item(item, platform, client, images_dir, videos_dir) for item in batch
    ]
    results = await asyncio.gather(*tasks)

    for res, item in zip(results, batch):
        if res.ok:
            if res.new_count:
                stats["downloaded"] += 1
                stats["bytes"] += res.size_bytes
                if res.media_type == "photo":
                    stats["images"] += 1
                elif res.media_type == "gif":
                    stats["gifs"] += 1
                else:
                    stats["videos"] += 1
            mark_downloaded(platform, item.source_id)
        elif res.error:
            errors[res.error] += 1


def _print_summary(stats: dict, errors: Counter, elapsed: float, interrupted: str | None) -> None:
    print("\n" + "=" * 65)
    print("🎉 DOWNLOAD CONCLUÍDO!" if not interrupted else "⚠️ DOWNLOAD INTERROMPIDO!")
    print(f"📊 Itens processados: {stats['processed']}")
    print(f"💾 Novas mídias baixadas: {stats['downloaded']}")

    if stats["downloaded"]:
        parts = []
        if stats["images"]:
            parts.append(f"🖼️ {stats['images']} imagens")
        if stats["videos"]:
            parts.append(f"🎬 {stats['videos']} vídeos")
        if stats["gifs"]:
            parts.append(f"🎞️ {stats['gifs']} gifs")
        if parts:
            print("   " + " | ".join(parts))
        print(f"📦 Tamanho total: {_fmt_size(stats['bytes'])}")

    print(f"⏱️ Tempo: {elapsed:.1f}s")

    if errors:
        print(f"⚠️ Falhas: {sum(errors.values())}")
        for reason, count in errors.most_common(5):
            print(f"   • {count}x {reason}")

    if interrupted:
        print(f"🛑 Motivo da interrupção: {interrupted}")

    print("=" * 65)


def _fmt_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"
