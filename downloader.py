#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
🦊 TWEET FOXDOWNLOADER 🦊
Utilitário assíncrono e ultra-rápido para baixar mídias (imagens, vídeos e GIFs) 
do Twitter/X utilizando autenticação estritamente via cookies do navegador.
"""

import asyncio
import os
import json
import sys
import io
import httpx
from pathlib import Path
from tqdm import tqdm
from twikit import Client

# Configurar saída padrão do terminal para UTF-8 no Windows para evitar erros de caractere
if sys.platform.startswith('win'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ------------------------------------------------------------------------------
# MONKEY PATCHES: Correções de Compatibilidade para twikit
# ------------------------------------------------------------------------------
try:
    import re
    import twikit.x_client_transaction.transaction as _tx_mod
    
    _tx_mod.ON_DEMAND_FILE_REGEX = re.compile(
        r""",(\d+):["\']ondemand\.s["\']""", flags=(re.VERBOSE | re.MULTILINE))
    _tx_mod.ON_DEMAND_HASH_PATTERN = r',{}:"([0-9a-f]+)"'

    async def _patched_get_indices(self, home_page_response, session, headers):
        key_byte_indices = []
        response = self.validate_response(home_page_response) or self.home_page_response
        on_demand_file_index = _tx_mod.ON_DEMAND_FILE_REGEX.search(str(response)).group(1)
        regex = re.compile(_tx_mod.ON_DEMAND_HASH_PATTERN.format(on_demand_file_index))
        filename = regex.search(str(response)).group(1)
        on_demand_file_url = f"https://abs.twimg.com/responsive-web/client-web/ondemand.s.{filename}a.js"
        
        on_demand_file_response = await session.request(method="GET", url=on_demand_file_url, headers=headers)
        key_byte_indices_match = _tx_mod.INDICES_REGEX.finditer(str(on_demand_file_response.text))
        
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
        elif 'data' in kwargs:
            data = kwargs['data']

        if isinstance(data, dict):
            defaults_data = {
                'withheld_in_countries': [],
                'pinned_tweet_ids_str': []
            }
            for k, v in defaults_data.items():
                if k not in data:
                    data[k] = v

            if 'legacy' in data:
                legacy = data['legacy']
                if isinstance(legacy, dict):
                    defaults_legacy = {
                        'withheld_in_countries': [],
                        'pinned_tweet_ids_str': [],
                        'entities': {},
                        'followers_count': 0,
                        'friends_count': 0,
                        'statuses_count': 0,
                        'favourites_count': 0,
                        'listed_count': 0,
                        'media_count': 0,
                        'verified': False,
                        'is_blue_verified': False
                    }
                    for k, v in defaults_legacy.items():
                        if k not in legacy:
                            legacy[k] = v

                    entities = legacy['entities']
                    if isinstance(entities, dict):
                        if 'description' not in entities:
                            entities['description'] = {}
                        description = entities['description']
                        if isinstance(description, dict) and 'urls' not in description:
                            description['urls'] = []
                        
                        if 'url' not in entities:
                            entities['url'] = {}
                        url_entity = entities['url']
                        if isinstance(url_entity, dict) and 'urls' not in url_entity:
                            url_entity['urls'] = []
                        
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
        elif 'data' in kwargs:
            data = kwargs['data']

        if isinstance(data, dict):
            defaults_data = {
                'withheld_in_countries': [],
                'pinned_tweet_ids_str': []
            }
            for k, v in defaults_data.items():
                if k not in data:
                    data[k] = v

            if 'legacy' in data:
                legacy = data['legacy']
                if isinstance(legacy, dict):
                    defaults_legacy = {
                        'withheld_in_countries': [],
                        'pinned_tweet_ids_str': []
                    }
                    for k, v in defaults_legacy.items():
                        if k not in legacy:
                            legacy[k] = v
        original_tweet_init(self, *args, **kwargs)
        
    Tweet.__init__ = patched_tweet_init
except Exception:
    pass

# ------------------------------------------------------------------------------
# GERENCIAMENTO DE HISTÓRICO E CONFIGURAÇÕES
# ------------------------------------------------------------------------------
COOKIES_FILE = "cookies.json"
HISTORY_FILE = "download_history.json"
DOWNLOAD_DELAY = 1.5  # Atraso em segundos entre chamadas de página para segurança da conta

# Carregar histórico global para não baixar duplicados
if Path(HISTORY_FILE).exists():
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            downloaded_history = set(json.load(f))
    except Exception:
        downloaded_history = set()
else:
    downloaded_history = set()

def save_history():
    """Salva o histórico de downloads concluídos de forma persistente."""
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(list(downloaded_history), f, indent=4)
    except Exception as e:
        print(f"⚠️ Erro ao salvar histórico: {e}")

# ------------------------------------------------------------------------------
# UTILITÁRIOS E AUXILIARES
# ------------------------------------------------------------------------------
def extract_user_id_from_cookies():
    """Tenta extrair o ID numérico do proprietário diretamente dos cookies (twid)."""
    try:
        if Path(COOKIES_FILE).exists():
            with open(COOKIES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Se for dicionário
            if isinstance(data, dict) and 'twid' in data:
                import urllib.parse
                decoded = urllib.parse.unquote(data['twid'])
                if '=' in decoded:
                    return decoded.split('=')[1]
            
            # Se for lista
            elif isinstance(data, list):
                for cookie in data:
                    if isinstance(cookie, dict) and cookie.get('name') == 'twid':
                        import urllib.parse
                        decoded = urllib.parse.unquote(cookie.get('value', ''))
                        if '=' in decoded:
                            return decoded.split('=')[1]
    except Exception:
        pass
    return None

async def authenticate_client():
    """Realiza a autenticação exclusivamente a partir do arquivo cookies.json."""
    client = Client('en-US')
    
    if not Path(COOKIES_FILE).exists():
        print(f"\n❌ Erro: O arquivo '{COOKIES_FILE}' não foi encontrado.")
        print("💡 Crie um arquivo 'cookies.json' na mesma pasta com os cookies exportados do seu navegador.")
        return None

    print(f"💾 Carregando sessão de '{COOKIES_FILE}'...")
    try:
        client.load_cookies(COOKIES_FILE)
        print("✅ Sessão autenticada carregada com sucesso!")
        return client
    except Exception as e:
        print(f"⚠️ Falha no carregamento direto. Tentando converter formato da extensão...")
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
                    return client
            print("❌ Estrutura incompatível em 'cookies.json'. Falta a chave 'auth_token'.")
        except Exception as conv_err:
            print(f"❌ Erro ao ler/converter cookies: {conv_err}")
    return None

def get_original_image_url(media_url):
    """Garante que a URL da imagem aponte para a versão original original em resolução máxima (4K/orig)."""
    if not media_url:
        return media_url
    if '?' in media_url:
        import urllib.parse
        parsed = urllib.parse.urlparse(media_url)
        params = urllib.parse.parse_qs(parsed.query)
        params['name'] = ['orig']
        new_query = urllib.parse.urlencode(params, doseq=True)
        return urllib.parse.urlunparse((
            parsed.scheme, parsed.netloc, parsed.path,
            parsed.params, new_query, parsed.fragment
        ))
    else:
        if media_url.endswith(':orig'):
            return media_url
        for suffix in [':large', ':medium', ':small', ':thumb']:
            if media_url.endswith(suffix):
                return media_url[:-len(suffix)] + ':orig'
        return media_url + ':orig'

# ------------------------------------------------------------------------------
# MOTOR DE DOWNLOAD CONCORRENTE
# ------------------------------------------------------------------------------
async def download_media_item(media, tweet_id, index, tweet_date, images_dir, videos_dir):
    """Gerencia o download individual de uma foto ou vídeo para as pastas corretas."""
    prefix = f"{tweet_date}_" if tweet_date else ""
    try:
        # Se for Foto
        if media.type == 'photo':
            file_name = f"{prefix}tweet_{tweet_id}_{index}.jpg"
            dest_path = images_dir / file_name
            if dest_path.exists():
                return True
            
            if hasattr(media, 'media_url') and media.media_url:
                orig_url = get_original_image_url(media.media_url)
                try:
                    async with httpx.AsyncClient(timeout=30.0) as http_client:
                        r = await http_client.get(orig_url)
                        if r.status_code == 200:
                            with open(dest_path, 'wb') as f:
                                f.write(r.content)
                            return True
                except Exception:
                    pass
            
            # Fallback nativo
            await media.download(str(dest_path))
            return True
            
        # Se for Vídeo ou GIF Animado
        elif media.type in ['video', 'animated_gif']:
            file_name = f"{prefix}tweet_{tweet_id}_{index}.mp4"
            dest_path = videos_dir / file_name
            if dest_path.exists():
                return True
            
            if hasattr(media, 'streams') and media.streams:
                best_stream = media.streams[-1]
                await best_stream.download(str(dest_path))
                return True
    except Exception as e:
        print(f"\n⚠️ Erro ao baixar mídia {index} do tweet {tweet_id}: {e}")
    return False

# ------------------------------------------------------------------------------
# FLUXO PRINCIPAL
# ------------------------------------------------------------------------------
async def main():
    print("=" * 65)
    print("      🦊 TWEET FOXDOWNLOADER - MULTI-DOWNLOADER DE MÍDIAS 🦊      ")
    print("=" * 65)

    client = await authenticate_client()
    if not client:
        return

    # Extrair ID de usuário da própria conta autenticada
    my_user_id = extract_user_id_from_cookies()
    if my_user_id:
        print(f"👤 Login ativo como Usuário ID: {my_user_id}")
    else:
        try:
            if hasattr(client, 'user_id'):
                my_user_id = client.user_id
                if asyncio.iscoroutine(my_user_id) or callable(my_user_id):
                    my_user_id = await my_user_id() if callable(my_user_id) else await my_user_id
            else:
                my_user_id = client._user_id
            print(f"👤 Login ativo como Usuário ID: {my_user_id}")
        except Exception:
            print("👤 Sessão carregada (não foi possível extrair ID numérico localmente).")

    print("\n--- MENU DE OPÇÕES DE DOWNLOAD ---")
    print("1. 💖 Mídias Curtidas (Likes) - Suas próprias curtidas")
    print("2. 📝 Seus Tweets e Retweets - Postagens publicadas no seu feed")
    print("3. 📸 Suas Mídias Postadas - Apenas mídias originais enviadas por você")
    print("4. 🔖 Tweets Salvos (Bookmarks) - Itens marcados como salvos")
    print("5. 🌟 Destaques (Highlights) - Tweets destacados no seu perfil")
    print("6. 🔍 Mídias de Outro Perfil Público - Baixar posts de outra conta do X")
    print("0. 🚪 Sair do programa")
    print("-" * 65)

    escolha = input("👉 Escolha uma opção (0-6): ").strip()
    if escolha == '0' or not escolha:
        print("Até logo!")
        return

    # Configurações dinâmicas de destino
    action_folder = "downloads"
    tweets_result = None
    target_username = "seu_perfil"
    likes_count = None

    try:
        # Opção 1: Mídias Curtidas (Likes)
        if escolha == '1':
            action_folder = "likes"
            print("📊 Verificando total de curtidas da sua conta...")
            if my_user_id:
                try:
                    user_info = await client.get_user_by_id(my_user_id)
                    if hasattr(user_info, 'favourites_count'):
                        likes_count = user_info.favourites_count
                        print(f"📈 Total estimado de curtidas: {likes_count}")
                except Exception:
                    pass
            print("\n⏳ Buscando seus likes...")
            tweets_result = await client.get_user_tweets(my_user_id, 'Likes')

        # Opção 2: Seus Tweets e Retweets
        elif escolha == '2':
            action_folder = "my_tweets"
            print("\n⏳ Buscando seus tweets...")
            tweets_result = await client.get_user_tweets(my_user_id, 'Tweets')

        # Opção 3: Suas Mídias Postadas
        elif escolha == '3':
            action_folder = "my_media"
            print("\n⏳ Buscando suas mídias postadas...")
            tweets_result = await client.get_user_tweets(my_user_id, 'Media')

        # Opção 4: Tweets Salvos (Bookmarks)
        elif escolha == '4':
            action_folder = "bookmarks"
            print("\n⏳ Buscando seus bookmarks salvos...")
            tweets_result = await client.get_bookmarks()

        # Opção 5: Destaques (Highlights)
        elif escolha == '5':
            action_folder = "highlights"
            print("\n⏳ Buscando seus tweets de destaque...")
            tweets_result = await client.get_user_highlights_tweets(my_user_id)

        # Opção 6: Mídias de Outro Perfil Público
        elif escolha == '6':
            target_username = input("👉 Digite o @ da conta desejada (ex: Twitter): ").strip().replace("@", "")
            if not target_username:
                print("❌ Usuário inválido.")
                return
            
            print(f"\n🔍 Buscando ID de @{target_username}...")
            try:
                user_obj = await client.get_user_by_screen_name(target_username)
                target_user_id = user_obj.id
                print(f"✅ ID da conta encontrada: {target_user_id}")
            except Exception as e:
                print(f"❌ Não foi possível encontrar a conta @{target_username}: {e}")
                return

            print("\nO que você deseja baixar desse perfil?")
            print(f"A) Posts e Retweets de @{target_username}")
            print(f"B) Apenas as Mídias postadas por @{target_username}")
            print(f"C) Mídias Curtidas (Likes) de @{target_username} (Apenas se o perfil for público)")
            sub_opcao = input("Escolha uma sub-opção (A/B/C): ").strip().upper()

            if sub_opcao == 'A':
                action_folder = f"user_{target_username}_tweets"
                tweets_result = await client.get_user_tweets(target_user_id, 'Tweets')
            elif sub_opcao == 'B':
                action_folder = f"user_{target_username}_media"
                tweets_result = await client.get_user_tweets(target_user_id, 'Media')
            elif sub_opcao == 'C':
                action_folder = f"user_{target_username}_likes"
                tweets_result = await client.get_user_tweets(target_user_id, 'Likes')
            else:
                print("❌ Sub-opção inválida.")
                return
        else:
            print("❌ Opção inválida.")
            return

    except Exception as e:
        print(f"❌ Erro ao buscar os tweets solicitados: {e}")
        return

    if not tweets_result:
        print("ℹ️ Nenhuma postagem ou tweet encontrado para processar.")
        return

    # Definir e criar pastas de download específicas da ação
    base_dir = Path("liked_media") / action_folder
    images_dir = base_dir / "images"
    videos_dir = base_dir / "videos"
    
    images_dir.mkdir(parents=True, exist_ok=True)
    videos_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 65)
    print(f"📂 Destino das Imagens: {images_dir.resolve()}")
    print(f"📂 Destino dos Vídeos: {videos_dir.resolve()}")
    print("=" * 65)

    tweets_checked = 0
    media_downloaded = 0
    
    # Progresso estimado
    total_estimado = likes_count if (escolha == '1' and likes_count) else None
    pbar = tqdm(desc="Processando Tweets", unit="tweet", total=total_estimado)

    # Processador de tweet individual
    async def process_tweet(tweet):
        # Evitar download se já está no histórico
        if tweet.id in downloaded_history:
            return 0

        if hasattr(tweet, 'media') and tweet.media:
            tweet_date = None
            if hasattr(tweet, 'created_at_datetime') and tweet.created_at_datetime:
                try:
                    tweet_date = tweet.created_at_datetime.strftime('%Y-%m-%d')
                except Exception:
                    pass
            
            # Executar downloads em paralelo para velocidade máxima
            tasks = [
                download_media_item(media_item, tweet.id, idx, tweet_date, images_dir, videos_dir) 
                for idx, media_item in enumerate(tweet.media)
            ]
            results = await asyncio.gather(*tasks)
            
            if any(results):
                downloaded_history.add(tweet.id)
                save_history()
                return sum(1 for r in results if r)
        return 0

    # Paginação principal genérica compatível com qualquer fonte de tweets
    while tweets_result:
        batch_tweets = []
        for tweet in tweets_result:
            tweets_checked += 1
            batch_tweets.append(tweet)

        if batch_tweets:
            # Processar lote inteiro concorrentemente
            tasks = [process_tweet(t) for t in batch_tweets]
            results = await asyncio.gather(*tasks)
            media_downloaded += sum(results)
            pbar.update(len(batch_tweets))
            
            # Respeitar a API com leve delay por lote
            await asyncio.sleep(DOWNLOAD_DELAY)

        # Buscar próxima página de resultados
        try:
            tweets_result = await tweets_result.next()
            await asyncio.sleep(0.5)
        except Exception:
            # Fim dos resultados ou rate limit
            break

    pbar.close()
    
    print("\n" + "=" * 65)
    print("🎉 TAREFA DE DOWNLOAD CONCLUÍDA! 🎉")
    print(f"📊 Tweets verificados nesta sessão: {tweets_checked}")
    print(f"💾 Novas mídias baixadas nesta sessão: {media_downloaded}")
    print(f"📦 Total acumulado no histórico geral: {len(downloaded_history)}")
    print("=" * 65)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n🛑 Processo interrompido pelo usuário. Até logo!")
        sys.exit(0)
