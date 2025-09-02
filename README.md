
# PubMed Chat検索 (Streamlit)

PubMed APIとOpenAI APIを組み合わせて、論文検索＋AI要約ができるアプリです。

## セットアップ手順（初心者向け）

### 1. GitHubにアップロード
- このフォルダの中身をGitHubにアップロード（リポジトリ例: pubmed-chat-app）

### 2. Streamlit Cloudでアプリを作成
- https://streamlit.io/cloud にアクセスしGitHubアカウントでログイン
- 「Create app」→ GitHubリポジトリを選択
- file path: app.py を指定

### 3. SecretsにAPIキーを設定
Streamlit Cloudの「Advanced settings」→「Secrets」に以下を入力：

```toml
PUBMED_API_KEY = "あなたのPubMed APIキー"
OPENAI_API_KEY = "あなたのOpenAI APIキー"
```

### 4. デプロイ
- 「Deploy」を押すと数分でアプリが公開され、URLが発行されます。

## ローカルで試す場合（Python環境がある場合）
```bash
pip install -r requirements.txt
streamlit run app.py
```

## 注意
- APIキーは必ずSecretsに入れて、コードに直接書かないでください。
- 無料枠を超えるとOpenAI APIには利用料金が発生します。
