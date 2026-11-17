# 🦊 FoxDownloader

Ferramenta em Python e executável (.exe) para fazer backup de **imagens (resolução máxima)**, **vídeos** e **GIFs** de múltiplas plataformas — tudo autenticado **sem usuário e senha**, apenas via cookies/tokens de sessão.

## Plataformas suportadas

| Plataforma  | Curtidas/Salvos | Postagens próprias | Outros perfis |
|-------------|-----------------|--------------------|---------------|
| Twitter / X | ✅ Likes        | ✅ Tweets, Mídias, Bookmarks, Highlights | ✅ Perfil público |
| Pixiv       | ✅ Bookmarks    | ✅ Illusts (illust + manga) | — |
| Pinterest   | ✅ Salvos (boards) | ✅ Pins criados | — |

---

## 🚀 Como usar o executável (.exe)

1. Coloque os arquivos de autenticação na mesma pasta do `downloader.exe` (veja abaixo).
2. Dê dois cliques no `downloader.exe`.
3. Escolha a plataforma e a ação desejada.

## 🐍 Como rodar via Python

```bash
pip install -r requirements.txt
python downloader.py
```

> Requer Python 3.10+ (por causa do `pinterest-dl`).

---

## 🔑 Autenticação por plataforma

Nenhuma plataforma pede senha. Você só precisa destes arquivos:

| Plataforma  | Arquivo           | Como obter |
|-------------|-------------------|------------|
| Twitter / X | `cookies.json`    | Exporte os cookies do navegador logado no X (ex.: extensão EditThisCookie). |
| Pixiv       | `pixiv_cookies.json` | Exporte os cookies do navegador logado no Pixiv (precisa conter o `PHPSESSID`). |
| Pinterest   | `pinterest_cookies.json` | `pinterest-dl login --from-browser -o pinterest_cookies.json` (ou exporte os cookies do navegador logado no Pinterest). Preencha também `"username"` em `config.json`. |

O arquivo `config.json` é criado automaticamente na primeira execução e permite trocar o caminho dos arquivos de cookies.

---

## 📁 Estrutura de pastas

Os downloads são organizados em:

```
downloads/
├── twitter/
│   ├── likes/images|videos/
│   ├── my_tweets/images|videos/
│   ├── my_media/images|videos/
│   ├── bookmarks/images|videos/
│   ├── highlights/images|videos/
│   └── user_profile_*/images|videos/
├── pixiv/
│   ├── bookmarks/images/  (e videos/ para UGOIRA → GIF)
│   └── own_illusts/images/
└── pinterest/
    ├── saved/images|videos/
    └── created/images|videos/
```

Os arquivos são nomeados como `{data}_{plataforma}_{id}_{índice}.ext` (a data aparece quando disponível).

---

## ⚙️ Observações e limitações

- **Pinterest** usa a API interna (`/resource/...`) com seus cookies. Como o Pinterest muda esses endpoints com frequência, pode ser necessário ajustar o adapter caso ele deixe de responder.
- **Pinterest — vídeos**: para converter vídeos para MP4 é recomendado ter o `ffmpeg` instalado no sistema. Sem ele, o download cai para a imagem (pôster) do pin.
- **Pixiv**: autentica pelo `PHPSESSID` dos cookies, usando a API web interna (`/ajax/...`). O ID do usuário é lido do próprio cookie — não é preciso gerar token.
- **Pixiv — UGOIRA**: obras animadas são convertidas para GIF (requer Pillow, já nas dependências).
- **Histórico**: o arquivo `download_history.json` evita baixar de novo o que já foi concluído. O formato antigo (lista de tweets) é migrado automaticamente.
- **Estatísticas**: ao autenticar, o programa exibe um resumo da conta (curtidas, posts, mídias etc.) e, ao final de cada download, mostra quantidades por tipo, tamanho total, tempo e eventuais falhas agrupadas por motivo.

---

## ⚠️ Segurança da conta

Guarde os arquivos `cookies.json`, `pixiv_cookies.json`, `pinterest_cookies.json` e `config.json` como segredos. Eles dão acesso à sua sessão. Não os compartilhe nem os comite no Git (o `.gitignore` já os ignora).
