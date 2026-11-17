# -*- coding: utf-8 -*-
"""Adapter do Twitter/X (twikit), com toda a lógica original preservada."""

import asyncio
import json
from pathlib import Path

from twikit import Client

from core.models import MediaItem
from platforms.base import PlatformAdapter, Action

COOKIES_FILE = "cookies.json"
PAGE_DELAY = 0.5

# ------------------------------------------------------------------------------
# MONKEY PATCHES: Correções de Compatibilidade para twikit
# ------------------------------------------------------------------------------
try:
    import re
    import twikit.x_client_transaction.transaction as _tx_mod

    _tx_mod.ON_DEMAND_FILE_REGEX = re.compile(
        r""",(\d+):["\']ondemand\.s["\']""", flags=(re.VERBOSE | re.MULTILINE)
    )
    _tx_mod.ON_DEMAND_HASH_PATTERN = r',{}:"([0-9a-f]+)"'

    async def _patched_get_indices(self, home_page_response, session, headers):
        key_byte_indices = []
        response = self.validate_response(home_page_response) or self.home_page_response
        on_demand_file_index = _tx_mod.ON_DEMAND_FILE_REGEX.search(str(response)).group(1)
        regex = re.compile(_tx_mod.ON_DEMAND_HASH_PATTERN.format(on_demand_file_index))
        filename = regex.search(str(response)).group(1)
        on_demand_file_url = (
            f"https://abs.twimg.com/responsive-web/client-web/ondemand.s.{filename}a.js"
        )

        on_demand_file_response = await session.request(
            method="GET", url=on_demand_file_url, headers=headers
        )
        key_byte_indices_match = _tx_mod.INDICES_REGEX.finditer(
            str(on_demand_file_response.text)
        )

        for item in key_byte_indices_match:
            key_byte_indices.append(item.group(2))

        if not key_byte_indices:
            raise Exception("Couldn't get KEY_BYTE indices")

        key_byte_indices = list(map(int, key_byte_indices))
        return key_byte_indices[0], key_byte_indices[1:]

    _tx_mod.ClientTransaction.get_indices = _patched_get_indices
except Exception:
    pass

try:
    from twikit.user import User

    original_user_init = User.__init__

    def patched_user_init(self, *args, **kwargs):
        data = None
        if len(args) > 1:
            data = args[1]
        elif "data" in kwargs:
            data = kwargs["data"]

        if isinstance(data, dict):
            defaults_data = {"withheld_in_countries": [], "pinned_tweet_ids_str": []}
            for k, v in defaults_data.items():
                if k not in data:
                    data[k] = v

            if "legacy" in data:
                legacy = data["legacy"]
                if isinstance(legacy, dict):
                    defaults_legacy = {
                        "withheld_in_countries": [],
                        "pinned_tweet_ids_str": [],
                        "entities": {},
                        "followers_count": 0,
                        "friends_count": 0,
                        "statuses_count": 0,
                        "favourites_count": 0,
                        "listed_count": 0,
                        "media_count": 0,
                        "verified": False,
                        "is_blue_verified": False,
                    }
                    for k, v in defaults_legacy.items():
                        if k not in legacy:
                            legacy[k] = v

                    entities = legacy["entities"]
                    if isinstance(entities, dict):
                        if "description" not in entities:
                            entities["description"] = {}
                        description = entities["description"]
                        if isinstance(description, dict) and "urls" not in description:
                            description["urls"] = []

                        if "url" not in entities:
                            entities["url"] = {}
                        url_entity = entities["url"]
                        if isinstance(url_entity, dict) and "urls" not in url_entity:
                            url_entity["urls"] = []

        original_user_init(self, *args, **kwargs)

    User.__init__ = patched_user_init
except Exception:
    pass

try:
    from twikit.tweet import Tweet

    original_tweet_init = Tweet.__init__

    def patched_tweet_init(self, *args, **kwargs):
        data = None
        if len(args) > 1:
            data = args[1]
        elif "data" in kwargs:
            data = kwargs["data"]

        if isinstance(data, dict):
            defaults_data = {"withheld_in_countries": [], "pinned_tweet_ids_str": []}
            for k, v in defaults_data.items():
                if k not in data:
                    data[k] = v

            if "legacy" in data:
                legacy = data["legacy"]
                if isinstance(legacy, dict):
                    defaults_legacy = {
                        "withheld_in_countries": [],
                        "pinned_tweet_ids_str": [],
                    }
                    for k, v in defaults_legacy.items():
                        if k not in legacy:
                            legacy[k] = v

        original_tweet_init(self, *args, **kwargs)

    Tweet.__init__ = patched_tweet_init
except Exception:
    pass


# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------
def extract_user_id_from_cookies():
    """Tenta extrair o ID numérico do proprietário diretamente dos cookies (twid)."""
    try:
        if Path(COOKIES_FILE).exists():
            with open(COOKIES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, dict) and "twid" in data:
                import urllib.parse

                decoded = urllib.parse.unquote(data["twid"])
                if "=" in decoded:
                    return decoded.split("=")[1]

            elif isinstance(data, list):
                for cookie in data:
                    if isinstance(cookie, dict) and cookie.get("name") == "twid":
                        import urllib.parse

                        decoded = urllib.parse.unquote(cookie.get("value", ""))
                        if "=" in decoded:
                            return decoded.split("=")[1]
    except Exception:
        pass
    return None


def get_original_image_url(media_url):
    """Garante a URL da imagem em resolução máxima (orig)."""
    if not media_url:
        return media_url

    if "?" in media_url:
        import urllib.parse

        parsed = urllib.parse.urlparse(media_url)
        params = urllib.parse.parse_qs(parsed.query)
        params["name"] = ["orig"]
        new_query = urllib.parse.urlencode(params, doseq=True)
        return urllib.parse.urlunparse(
            (parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment)
        )

    if media_url.endswith(":orig"):
        return media_url
    for suffix in (":large", ":medium", ":small", ":thumb"):
        if media_url.endswith(suffix):
            return media_url[: -len(suffix)] + ":orig"
    return media_url + ":orig"


def _tweet_date(tweet):
    if hasattr(tweet, "created_at_datetime") and tweet.created_at_datetime:
        try:
            return tweet.created_at_datetime.strftime("%Y-%m-%d")
        except Exception:
            pass
    return None


# ------------------------------------------------------------------------------
# Adapter
# ------------------------------------------------------------------------------
class TwitterAdapter(PlatformAdapter):
    name = "twitter"
    display_name = "Twitter / X"

    def __init__(self, config, history):
        super().__init__(config, history)
        self.client = None
        self.my_user_id = None
        self._profile_username = None
        self._profile_user_id = None

    async def authenticate(self) -> bool:
        client = Client("en-US")

        if not Path(COOKIES_FILE).exists():
            print(f"\n❌ Erro: O arquivo '{COOKIES_FILE}' não foi encontrado.")
            print(
                "💡 Crie um arquivo 'cookies.json' na mesma pasta com os cookies "
                "exportados do seu navegador."
            )
            return False

        print(f"💾 Carregando sessão de '{COOKIES_FILE}'...")
        try:
            client.load_cookies(COOKIES_FILE)
            print("✅ Sessão autenticada carregada com sucesso!")
        except Exception:
            print("⚠️ Falha no carregamento direto. Tentando converter formato da extensão...")
            try:
                with open(COOKIES_FILE, "r", encoding="utf-8") as f:
                    cookies_data = json.load(f)

                if isinstance(cookies_data, list):
                    cookies_dict = {}
                    for cookie in cookies_data:
                        if isinstance(cookie, dict) and "name" in cookie and "value" in cookie:
                            cookies_dict[cookie["name"]] = cookie["value"]

                    if "auth_token" in cookies_dict:
                        client.set_cookies(cookies_dict)
                        client.save_cookies(COOKIES_FILE)
                        print("✅ Cookies convertidos e salvos no formato ideal!")
                    else:
                        print("❌ Estrutura incompatível em 'cookies.json'. Falta 'auth_token'.")
                        return False
            except Exception as conv_err:
                print(f"❌ Erro ao ler/converter cookies: {conv_err}")
                return False

        self.client = client
        self.my_user_id = extract_user_id_from_cookies()

        if not self.my_user_id:
            try:
                if hasattr(client, "user_id"):
                    self.my_user_id = client.user_id
                    if asyncio.iscoroutine(self.my_user_id) or callable(self.my_user_id):
                        self.my_user_id = (
                            await self.my_user_id()
                            if callable(self.my_user_id)
                            else await self.my_user_id
                        )
                else:
                    self.my_user_id = client._user_id
            except Exception:
                pass

        if self.my_user_id:
            print(f"👤 Login ativo como Usuário ID: {self.my_user_id}")
        else:
            print("👤 Sessão carregada (não foi possível extrair ID numérico localmente).")

        return True

    def actions(self) -> list[Action]:
        return [
            Action("likes", "💖 Mídias Curtidas (Likes)", "likes", self._fetch_likes),
            Action("my_tweets", "📝 Seus Tweets e Retweets", "my_tweets", self._fetch_tweets),
            Action("my_media", "📸 Suas Mídias Postadas", "my_media", self._fetch_media),
            Action("bookmarks", "🔖 Tweets Salvos (Bookmarks)", "bookmarks", self._fetch_bookmarks),
            Action("highlights", "🌟 Destaques (Highlights)", "highlights", self._fetch_highlights),
        ]

    async def extra_actions(self) -> list[Action]:
        return [
            Action(
                "other_tweets",
                "🔍 Outro Perfil — Posts e Retweets",
                "user_profile_tweets",
                self._fetch_other_tweets,
            ),
            Action(
                "other_media",
                "🔍 Outro Perfil — Apenas Mídias",
                "user_profile_media",
                self._fetch_other_media,
            ),
            Action(
                "other_likes",
                "🔍 Outro Perfil — Curtidas",
                "user_profile_likes",
                self._fetch_other_likes,
            ),
        ]

    async def summary(self) -> list[str]:
        if not self.my_user_id:
            return []
        try:
            user = await self.client.get_user_by_id(self.my_user_id)
        except Exception as e:
            return [f"⚠️ Não foi possível ler o resumo da conta ({type(e).__name__})."]

        lines = []
        screen_name = getattr(user, "screen_name", None)
        name = getattr(user, "name", None)
        if screen_name:
            lines.append(f"👤 @{screen_name}" + (f" ({name})" if name else ""))

        stats = []
        for attr, label in (
            ("favourites_count", "💖 Curtidas"),
            ("statuses_count", "📝 Posts"),
            ("media_count", "📸 Mídias"),
            ("followers_count", "👥 Seguidores"),
            ("friends_count", "➡️ Seguindo"),
        ):
            value = getattr(user, attr, None)
            if isinstance(value, int):
                stats.append(f"{label}: {value:,}")
        if stats:
            lines.append(" | ".join(stats))
        return lines

    # ------------------------------------------------------------------
    # Fetch próprios
    # ------------------------------------------------------------------
    async def _fetch_likes(self):
        result = await self.client.get_user_tweets(self.my_user_id, "Likes")
        async for item in self._iter_tweets(result):
            yield item

    async def _fetch_tweets(self):
        result = await self.client.get_user_tweets(self.my_user_id, "Tweets")
        async for item in self._iter_tweets(result):
            yield item

    async def _fetch_media(self):
        result = await self.client.get_user_tweets(self.my_user_id, "Media")
        async for item in self._iter_tweets(result):
            yield item

    async def _fetch_bookmarks(self):
        result = await self.client.get_bookmarks()
        async for item in self._iter_tweets(result):
            yield item

    async def _fetch_highlights(self):
        result = await self.client.get_user_highlights_tweets(self.my_user_id)
        async for item in self._iter_tweets(result):
            yield item

    async def _iter_tweets(self, result):
        while result:
            for tweet in result:
                for item in self._tweet_to_items(tweet):
                    yield item
            try:
                result = await result.next()
                await asyncio.sleep(PAGE_DELAY)
            except Exception:
                break

    # ------------------------------------------------------------------
    # Outro perfil
    # ------------------------------------------------------------------
    async def _prompt_profile(self) -> bool:
        if self._profile_user_id:
            return True

        username = (
            input("👉 Digite o @ da conta desejada (ex: Twitter): ")
            .strip()
            .replace("@", "")
        )
        if not username:
            print("❌ Usuário inválido.")
            return False

        try:
            user_obj = await self.client.get_user_by_screen_name(username)
            self._profile_username = username
            self._profile_user_id = user_obj.id
            print(f"✅ ID da conta encontrada: {self._profile_user_id}")
            return True
        except Exception as e:
            print(f"❌ Não foi possível encontrar a conta @{username}: {e}")
            return False

    async def _fetch_other_tweets(self):
        if not await self._prompt_profile():
            return
        result = await self.client.get_user_tweets(self._profile_user_id, "Tweets")
        async for item in self._iter_tweets(result):
            yield item

    async def _fetch_other_media(self):
        if not await self._prompt_profile():
            return
        result = await self.client.get_user_tweets(self._profile_user_id, "Media")
        async for item in self._iter_tweets(result):
            yield item

    async def _fetch_other_likes(self):
        if not await self._prompt_profile():
            return
        result = await self.client.get_user_tweets(self._profile_user_id, "Likes")
        async for item in self._iter_tweets(result):
            yield item

    # ------------------------------------------------------------------
    # Conversão
    # ------------------------------------------------------------------
    def _tweet_to_items(self, tweet) -> list[MediaItem]:
        if not (hasattr(tweet, "media") and tweet.media):
            return []

        date = _tweet_date(tweet)
        source_id = str(tweet.id)
        items = []

        idx = 0
        for media in tweet.media:
            media_type = getattr(media, "type", None)

            if media_type == "photo":
                url = None
                if hasattr(media, "media_url") and media.media_url:
                    url = get_original_image_url(media.media_url)
                items.append(
                    MediaItem(
                        source_id=source_id,
                        media_type="photo",
                        url=url,
                        index=idx,
                        date=date,
                        extra={"downloadable": media},
                    )
                )
                idx += 1

            elif media_type in ("video", "animated_gif"):
                stream = None
                if hasattr(media, "streams") and media.streams:
                    stream = media.streams[-1]
                extra = {"downloadable": stream} if stream else {}
                items.append(
                    MediaItem(
                        source_id=source_id,
                        media_type="video",
                        url=getattr(stream, "url", None),
                        index=idx,
                        date=date,
                        extra=extra,
                    )
                )
                idx += 1

        return items
