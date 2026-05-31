# 🦊 Tweet FoxDownloader

**Tweet FoxDownloader** é uma ferramenta em Python e Executável (.exe) poderosa, ultra-rápida e extremamente segura desenvolvida para fazer backup automático de **todas as imagens (na resolução máxima original 4K)** e **vídeos/GIFs** da sua conta do Twitter/X ou de qualquer perfil público.

Para garantir a **segurança total da sua conta**, a ferramenta opera **estritamente via cookies de sessão (`cookies.json`)**. Isso significa que você **nunca** precisará fornecer seu usuário, e-mail ou senha!

---

## 🚀 Como Usar o Executável Direto (Método Mais Fácil)

Criamos uma versão executável independente para você rodar em qualquer computador sem precisar ter o Python ou qualquer biblioteca instalada!

1.  Vá para a pasta **`dist`** no diretório do projeto.
2.  Lá você encontrará o arquivo **`downloader.exe`**.
3.  Coloque o seu arquivo **`cookies.json`** na **mesma pasta** que o `downloader.exe`.
4.  Dê dois cliques no **`downloader.exe`** para iniciar o programa com o menu interativo!

---

## ✨ O que é possível baixar?

Com o **Tweet FoxDownloader**, você pode selecionar exatamente qual tipo de mídia deseja exportar através de um menu interativo no terminal:

1. 💖 **Mídias Curtidas (Likes)**: Faz o backup de todas as fotos e vídeos curtidos por você.
2. 📝 **Seus Tweets e Retweets**: Salva as mídias postadas diretamente no seu feed pessoal.
3. 📸 **Suas Mídias Postadas**: Filtro focado exclusivamente nas mídias que você enviou ao Twitter.
4. 🔖 **Tweets Salvos (Bookmarks)**: Faz o backup de todos os seus itens marcados como salvos na plataforma.
5. 🌟 **Destaques (Highlights)**: Baixa as mídias das postagens que você destacou no seu perfil.
6. 🔍 **Mídias de Outro Perfil Público**: Permite digitar o `@` de qualquer conta pública e baixar:
   - Posts e Retweets
   - Apenas mídias postadas
   - Curtidas (caso os likes daquela conta sejam públicos)

---

## 🛠️ Como Gerar o `cookies.json` (Em 1 Minuto)

Como o script funciona exclusivamente via cookies (garantindo que você não precise digitar login ou senha), basta exportá-los do seu navegador:

1.  Abra o navegador e faça login na sua conta do **Twitter/X** normalmente.
2.  Instale uma extensão segura de exportação de cookies, como a **[EditThisCookie](https://chromewebstore.google.com/detail/editthiscookie-v3/ojfebgpkimhlhcblbalbfjblapadhbol)**.
3.  Com a página do Twitter/X aberta, clique no ícone da extensão no topo direito do navegador e clique no botão **Exportar** (ícone de seta saindo `📤`). Isso copiará os cookies em formato JSON para a sua área de transferência (Ctrl+C).
4.  Crie um arquivo chamado **`cookies.json`** na mesma pasta do executável (ou do script), abra-o, cole o conteúdo copiado (Ctrl+V) e salve.

---

## 🐍 Executando Via Código Python (Opcional)

Se preferir rodar diretamente como desenvolvedor via código-fonte Python:

1.  Instale as dependências essenciais:
    ```bash
    pip install -r requirements.txt
    ```
2.  Execute o script:
    ```bash
    python downloader.py
    ```

---

## 📂 Estrutura Organizada de Pastas

Para manter tudo arrumado, os downloads de mídias são salvos em subpastas organizadas de acordo com a ação escolhida dentro do diretório `liked_media/`:

*   `liked_media/likes/`: Mídias curtidas por você.
*   `liked_media/my_tweets/`: Mídias do seu próprio feed.
*   `liked_media/my_media/`: Apenas suas mídias enviadas.
*   `liked_media/bookmarks/`: Mídias das suas postagens salvas.
*   `liked_media/highlights/`: Mídias das postagens em destaque.
*   `liked_media/user_[username]_[tipo]/`: Mídias obtidas de outros perfis pesquisados.

Os arquivos de mídia são ordenados e nomeados com a data do tweet no começo (`ANO-MES-DIA_tweet_[ID]_[INDEX].jpg/mp4`) para facilitar a navegação cronológica no seu computador!
