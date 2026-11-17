# -*- coding: utf-8 -*-
"""Adapter do Pinterest (API interna + pinterest-dl para download de vídeo)."""

import asyncio
import json
import shutil
import tempfile
import time
from pathlib import Path
from urllib.parse import urlencode

import httpx
from pinterest_dl.parsers.response import ResponseParser

from core.models import MediaItem
from platforms.base import PlatformAdapter, Action

PINTEREST_BASE = "https://www.pinterest.com"
PAGE_DELAY = 0.3
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def _short_error(exc: Exception) -> str:
    text = str(exc).strip().replace("\n", " ")
    return text[:140]


class PinterestAdapter(PlatformAdapter):
    name = "pinterest"
    display_name = "Pinterest"

    def __init__(self, config, history):
        super().__init__(config, history)
        cfg = config.get("pinterest") or {}
        self.username = cfg.get("username", "").strip()
        self.cookies_file = cfg.get("cookies_file", "pinterest_cookies.json")
        self._client = None
        self._boards_cache = None

    async def authenticate(self) -> bool:
        if not Path(self.cookies_file).exists():
            print(f"\n❌ Arquivo '{self.cookies_file}' não encontrado.")
            print(
                "💡 Gere com: pinterest-dl login --from-browser -o pinterest_cookies.json"
            )
            return False

        try:
            with open(self.cookies_file, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            if not isinstance(cookies, list):
                print("❌ Formato de cookies inválido (esperado: lista de cookies).")
                return False

            cookie_dict = {
                c.get("name"): c.get("value")
                for c in cookies
                if isinstance(c, dict) and c.get("name")
            }
        except Exception as e:
            print(f"❌ Erro ao ler cookies do Pinterest: {e}")
            return False

        self._client = httpx.AsyncClient(
            headers={
                "User-Agent": USER_AGENT,
                "X-Requested-With": "XMLHttpRequest",
                "Referer": "https://www.pinterest.com/",
                "x-pinterest-pws-handler": "www/pin/[id].js",
            },
            cookies=cookie_dict,
            timeout=30.0,
            follow_redirects=True,
        )

        if not self.username:
            self.username = input("👉 Digite seu username do Pinterest: ").strip().replace("@", "")
        if not self.username:
            print("❌ Username inválido.")
            await self.close()
            return False

        print(f"👤 Usuário Pinterest: {self.username}")
        return True

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def actions(self) -> list[Action]:
        return [
            Action("saved", "💖 Curtidas/Salvos (boards)", "saved", self._fetch_saved),
            Action("created", "📝 Postagens próprias (criados)", "created", self._fetch_created),
        ]

    async def summary(self) -> list[str]:
        if not self.username:
            return []
        lines = [f"👤 @{self.username}"]
        try:
            boards = await self._list_boards()
        except Exception as e:
            lines.append(f"⚠️ Não foi possível ler o resumo ({type(e).__name__}).")
            return lines

        total_pins = sum(b.get("pin_count") or 0 for b in boards)
        stats = [f"📌 Boards: {len(boards):,}"]
        if total_pins:
            stats.append(f"💾 Pins salvos (aprox.): {total_pins:,}")
        lines.append(" | ".join(stats))
        return lines

    async def _resource_get(self, resource: str, options: dict, source_url: str = "/") -> dict | None:
        data = json.dumps({"options": options, "context": {}})
        query = urlencode(
            {
                "source_url": source_url,
                "data": data,
                "_": str(int(time.time() * 1000)),
            }
        ).replace("+", "%20")
        url = f"{PINTEREST_BASE}/resource/{resource}/get/?{query}"
        try:
            resp = await self._client.get(url)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"⚠️ Erro na API Pinterest ({resource}): {_short_error(e)}")
            return None

    async def _list_boards(self) -> list[dict]:
        if self._boards_cache is not None:
            return self._boards_cache

        boards = []
        bookmarks = []
        while True:
            data = await self._resource_get(
                "BoardsResource",
                {
                    "username": self.username,
                    "field_set_key": "profile_grid_item",
                    "page_size": 25,
                    "bookmarks": bookmarks,
                },
                source_url=f"/{self.username}/",
            )
            if not data:
                break

            rr = data.get("resource_response") or {}
            for board in rr.get("data") or []:
                if not isinstance(board, dict) or not board.get("id"):
                    continue
                boards.append(
                    {
                        "id": board.get("id"),
                        "name": board.get("name") or board.get("slug"),
                        "url": board.get("url") or f"/{self.username}/",
                        "pin_count": board.get("pin_count"),
                    }
                )

            bookmark = rr.get("bookmark")
            if not bookmark or bookmark == "-end-":
                break
            bookmarks = [bookmark]
            await asyncio.sleep(PAGE_DELAY)

        self._boards_cache = boards
        return boards

    async def _iter_board_pins(self, board: dict):
        board_id = str(board.get("id"))
        source_url = board.get("url") or f"/{self.username}/"
        bookmarks = []
        seen = set()
        while True:
            data = await self._resource_get(
                "BoardFeedResource",
                {
                    "board_id": board_id,
                    "board_url": source_url,
                    "page_size": 50,
                    "bookmarks": bookmarks,
                    "currentFilter": -1,
                    "field_set_key": "react_grid_pin",
                    "filter_section_pins": True,
                    "sort": "default",
                    "layout": "default",
                    "redux_normalize_feed": True,
                },
                source_url=source_url,
            )
            if not data:
                break

            rr = data.get("resource_response") or {}
            for media in self._parse_media(rr.get("data") or []):
                media_id = str(getattr(media, "id", "") or "")
                if media_id:
                    if media_id in seen:
                        continue
                    seen.add(media_id)
                yield media

            bookmark = rr.get("bookmark")
            if not bookmark or bookmark == "-end-":
                break
            bookmarks = [bookmark]
            await asyncio.sleep(PAGE_DELAY)

    async def _iter_created_pins(self):
        bookmarks = []
        seen = set()
        while True:
            data = await self._resource_get(
                "UserPinsResource",
                {
                    "username": self.username,
                    "field_set_key": "grid_item",
                    "page_size": 25,
                    "bookmarks": bookmarks,
                },
                source_url=f"/{self.username}/",
            )
            if not data:
                break

            rr = data.get("resource_response") or {}
            for media in self._parse_media(rr.get("data") or []):
                media_id = str(getattr(media, "id", "") or "")
                if media_id:
                    if media_id in seen:
                        continue
                    seen.add(media_id)
                yield media

            bookmark = rr.get("bookmark")
            if not bookmark or bookmark == "-end-":
                break
            bookmarks = [bookmark]
            await asyncio.sleep(PAGE_DELAY)

    def _parse_media(self, items):
        try:
            return ResponseParser.from_responses(items, (0, 0))
        except Exception:
            return []

    async def _fetch_saved(self):
        boards = await self._list_boards()
        if not boards:
            print("⚠️ Nenhum board encontrado para este usuário.")
            return
        print(f"📊 {len(boards)} boards encontrados.")

        for board in boards:
            async for pin in self._iter_board_pins(board):
                for item in self._pin_to_items(pin):
                    yield item

    async def _fetch_created(self):
        async for pin in self._iter_created_pins():
            for item in self._pin_to_items(pin):
                yield item

    def _pin_to_items(self, pin) -> list[MediaItem]:
        source_id = str(getattr(pin, "id", "") or "")

        video_stream = getattr(pin, "video_stream", None)
        if video_stream and getattr(video_stream, "url", None):
            return [
                MediaItem(
                    source_id=source_id,
                    media_type="video",
                    url=None,
                    index=0,
                    extra={"download_fn": self._make_pin_video_downloader(pin)},
                )
            ]

        src = getattr(pin, "src", None)
        if src:
            return [
                MediaItem(
                    source_id=source_id,
                    media_type="photo",
                    url=src,
                    index=0,
                )
            ]

        return []

    def _make_pin_video_downloader(self, pin):
        async def download_fn(dest_path):
            return await asyncio.to_thread(self._download_pin_video_sync, pin, dest_path)

        return download_fn

    def _download_pin_video_sync(self, pin, dest_path) -> bool:
        try:
            from pinterest_dl.scrapers.operations import download_media as pin_download

            with tempfile.TemporaryDirectory() as tmp:
                items = pin_download([pin], tmp, download_streams=True, skip_remux=False)
                if items and items[0].local_path:
                    src = Path(items[0].local_path)
                    if src.exists():
                        ext = src.suffix or ".mp4"
                        final = dest_path.with_suffix(ext)
                        shutil.move(str(src), str(final))
                        return True
        except Exception as e:
            print(f"⚠️ Erro ao baixar vídeo do Pinterest ({getattr(pin, 'id', '')}): {e}")
        return False
