# -*- coding: utf-8 -*-
"""Adapter do Pixiv usando a API web interna (autenticação por cookies/PHPSESSID)."""

import asyncio
import io
import json
import zipfile
from pathlib import Path

import httpx

from core.models import MediaItem
from platforms.base import PlatformAdapter, Action

BASE = "https://www.pixiv.net"
REFERER = "https://www.pixiv.net/"
PAGE_DELAY = 0.4
DEFAULT_COOKIES_FILE = "pixiv_cookies.json"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def _ids_from(obj) -> list[str]:
    """Extrai uma lista de IDs tanto de dict {id: ...} quanto de lista."""
    if isinstance(obj, dict):
        return [str(k) for k in obj.keys()]
    if isinstance(obj, list):
        result = []
        for entry in obj:
            if isinstance(entry, dict):
                result.append(str(entry.get("id")))
            else:
                result.append(str(entry))
        return [i for i in result if i and i != "None"]
    return []


class PixivAdapter(PlatformAdapter):
    name = "pixiv"
    display_name = "Pixiv"

    def __init__(self, config, history):
        super().__init__(config, history)
        cfg = config.get("pixiv") or {}
        self.cookies_file = cfg.get("cookies_file") or DEFAULT_COOKIES_FILE
        self.user_id = None
        self.username = None
        self.client = None

    async def authenticate(self) -> bool:
        path = Path(self.cookies_file)
        if not path.exists():
            for candidate in ("pixiv_cookies.json", "www.pixiv.net_cookies.json"):
                if Path(candidate).exists():
                    path = Path(candidate)
                    break
        if not path.exists():
            print(f"\n❌ Arquivo de cookies '{self.cookies_file}' não encontrado.")
            print(
                "💡 Exporte os cookies de pixiv.net (logado) para esse arquivo "
                "(ex.: extensão de exportar cookies)."
            )
            return False

        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception as e:
            print(f"❌ Erro ao ler cookies do Pixiv: {e}")
            return False

        if isinstance(raw, dict):
            cookie_dict = {k: v for k, v in raw.items() if isinstance(v, str)}
        elif isinstance(raw, list):
            cookie_dict = {
                c.get("name"): c.get("value")
                for c in raw
                if isinstance(c, dict) and c.get("name")
            }
        else:
            print("❌ Formato de cookies inválido.")
            return False

        php_sessid = cookie_dict.get("PHPSESSID")
        if not php_sessid:
            print("❌ 'PHPSESSID' não encontrado nos cookies (faça login no Pixiv).")
            return False

        if "_" in php_sessid:
            self.user_id = php_sessid.split("_")[0]

        self.client = httpx.AsyncClient(
            cookies=cookie_dict,
            headers={
                "User-Agent": USER_AGENT,
                "Referer": REFERER,
                "Accept": "application/json",
            },
            timeout=30.0,
            follow_redirects=True,
        )

        try:
            data = await self._ajax_get("/ajax/user/extra")
        except Exception as e:
            print(f"❌ Erro ao validar a sessão do Pixiv: {e}")
            await self.close()
            return False

        if not data or data.get("error"):
            print("❌ Sessão do Pixiv inválida ou expirada. Exporte os cookies novamente.")
            await self.close()
            return False

        await self._load_username()

        who = f"@{self.username}" if self.username else "sessão ativa"
        print(f"👤 Login Pixiv ativo: {who} (ID {self.user_id})")
        return True

    async def _load_username(self) -> None:
        if not self.user_id:
            return
        try:
            data = await self._ajax_get(f"/ajax/user/{self.user_id}", {"full": 1})
            self.username = (data.get("body") or {}).get("name")
        except Exception:
            pass

    async def close(self) -> None:
        if self.client is not None:
            await self.client.aclose()
            self.client = None

    def actions(self) -> list[Action]:
        return [
            Action("bookmarks", "💖 Curtidas (Bookmarks)", "bookmarks", self._fetch_bookmarks),
            Action("own_illusts", "📝 Postagens próprias (Illusts)", "own_illusts", self._fetch_own_illusts),
        ]

    async def summary(self) -> list[str]:
        if not self.user_id:
            return []

        lines = []
        if self.username:
            lines.append(f"👤 @{self.username} (ID {self.user_id})")
        else:
            lines.append(f"👤 ID {self.user_id}")

        stats = []

        # O bookmarkCount do profile/all é impreciso; o total vem do endpoint de bookmarks.
        for rest, label in (("show", "💖 Curtidas (públicas)"), ("hide", "🔒 Curtidas (privadas)")):
            try:
                data = await self._ajax_get(
                    f"/ajax/user/{self.user_id}/illusts/bookmarks",
                    {"tag": "", "offset": 0, "limit": 1, "rest": rest},
                )
                total = (data.get("body") or {}).get("total")
                if isinstance(total, int):
                    stats.append(f"{label}: {total:,}")
            except Exception:
                pass

        try:
            data = await self._ajax_get(f"/ajax/user/{self.user_id}/profile/all")
            body = data.get("body") or {}
            own = len(_ids_from(body.get("illusts"))) + len(_ids_from(body.get("manga")))
            stats.append(f"📝 Obras próprias: {own:,}")
        except Exception:
            pass

        if stats:
            lines.append(" | ".join(stats))
        return lines

    # ------------------------------------------------------------------
    # API interna
    # ------------------------------------------------------------------
    async def _ajax_get(self, path: str, params: dict | None = None) -> dict:
        resp = await self.client.get(f"{BASE}{path}", params=params or {})
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Ações
    # ------------------------------------------------------------------
    async def _fetch_bookmarks(self):
        if not self.user_id:
            print("⚠️ Não foi possível determinar seu ID do Pixiv.")
            return

        offset = 0
        limit = 48
        while True:
            try:
                data = await self._ajax_get(
                    f"/ajax/user/{self.user_id}/illusts/bookmarks",
                    {"tag": "", "offset": offset, "limit": limit, "rest": "show"},
                )
            except Exception as e:
                print(f"⚠️ Erro ao buscar bookmarks: {e}")
                break

            works = (data.get("body") or {}).get("works") or []
            if not works:
                break

            for work in works:
                async for item in self._work_to_items(str(work.get("id"))):
                    yield item
                await asyncio.sleep(0.2)

            offset += len(works)
            if len(works) < limit:
                break
            await asyncio.sleep(PAGE_DELAY)

    async def _fetch_own_illusts(self):
        if not self.user_id:
            print("⚠️ Não foi possível determinar seu ID do Pixiv.")
            return

        try:
            data = await self._ajax_get(f"/ajax/user/{self.user_id}/profile/all")
        except Exception as e:
            print(f"⚠️ Erro ao buscar suas obras: {e}")
            return

        body = data.get("body") or {}
        ids = _ids_from(body.get("illusts")) + _ids_from(body.get("manga"))

        if not ids:
            print("ℹ️ Nenhuma obra própria encontrada.")
            return

        for illust_id in ids:
            async for item in self._work_to_items(illust_id):
                yield item
            await asyncio.sleep(0.2)

    # ------------------------------------------------------------------
    # Conversão de uma obra em MediaItem(s)
    # ------------------------------------------------------------------
    async def _work_to_items(self, illust_id: str):
        try:
            data = await self._ajax_get(f"/ajax/illust/{illust_id}")
        except Exception as e:
            print(f"⚠️ Erro ao buscar detalhes da obra {illust_id}: {e}")
            return

        body = data.get("body") or {}
        if not body:
            return

        date = (body.get("createDate") or "")[:10].replace("/", "-") or None
        illust_type = body.get("illustType")

        if illust_type == 2:
            async for item in self._yield_ugoira(illust_id, date):
                yield item
            return

        page_count = body.get("pageCount") or 1
        if page_count > 1:
            try:
                pages = await self._ajax_get(f"/ajax/illust/{illust_id}/pages")
            except Exception:
                pages = {}
            for idx, page in enumerate(pages.get("body") or []):
                url = (page.get("urls") or {}).get("original")
                if url:
                    yield MediaItem(
                        source_id=illust_id,
                        media_type="photo",
                        url=url,
                        index=idx,
                        date=date,
                        referer=REFERER,
                    )
        else:
            url = (body.get("urls") or {}).get("original")
            if url:
                yield MediaItem(
                    source_id=illust_id,
                    media_type="photo",
                    url=url,
                    index=0,
                    date=date,
                    referer=REFERER,
                )

    async def _yield_ugoira(self, illust_id: str, date):
        try:
            meta = await self._ajax_get(f"/ajax/illust/{illust_id}/ugoira_meta")
        except Exception as e:
            print(f"⚠️ Erro ao buscar ugoira {illust_id}: {e}")
            return

        body = meta.get("body") or {}
        zip_url = body.get("originalSrc") or body.get("src")
        if not zip_url:
            return

        frames = body.get("frames") or []
        yield MediaItem(
            source_id=illust_id,
            media_type="gif",
            index=0,
            date=date,
            referer=REFERER,
            extra={"download_fn": self._make_ugoira_downloader(zip_url, frames)},
        )

    def _make_ugoira_downloader(self, zip_url: str, frames: list):
        async def download_fn(dest_path):
            return await asyncio.to_thread(self._build_ugoira_gif, zip_url, frames, dest_path)

        return download_fn

    def _build_ugoira_gif(self, zip_url: str, frames: list, dest_path) -> bool:
        try:
            with httpx.Client(
                headers={"Referer": REFERER, "User-Agent": USER_AGENT},
                timeout=60.0,
                follow_redirects=True,
            ) as client:
                resp = client.get(zip_url)
                if resp.status_code != 200:
                    return False
                content = resp.content

            delays = [int(f.get("delay", 80) or 80) for f in frames]

            from PIL import Image

            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                names = sorted(
                    n for n in zf.namelist() if n.lower().endswith((".jpg", ".jpeg", ".png"))
                )
                images = [
                    Image.open(io.BytesIO(zf.read(name))).convert("RGBA") for name in names
                ]

            if not images:
                return False
            if not delays or len(delays) != len(images):
                delays = [80] * len(images)

            images[0].save(
                str(dest_path),
                save_all=True,
                append_images=images[1:],
                duration=delays,
                loop=0,
            )
            return True
        except Exception as e:
            print(f"⚠️ Erro ao converter ugoira: {e}")
            return False
