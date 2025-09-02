import requests
import xml.etree.ElementTree as ET
import streamlit as st
from openai import OpenAI  # ← 新しいSDKの書き方

# --- SecretsからAPIキーを取得 ---
PUBMED_API_KEY = st.secrets["PUBMED_API_KEY"]
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]

client = OpenAI(api_key=OPENAI_API_KEY)

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"

def esearch(term: str, retmax: int = 5):
    params = {"db": "pubmed", "term": term, "retmax": retmax, "retmode": "json", "api_key": PUBMED_API_KEY}
    r = requests.get(BASE + "esearch.fcgi", params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data.get("esearchresult", {}).get("idlist", [])

def efetch(pmids):
    if not pmids:
        return []
    params = {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml", "api_key": PUBMED_API_KEY}
    r = requests.get(BASE + "efetch.fcgi", params=params, timeout=60)
    r.raise_for_status()
    root = ET.fromstring(r.text)
    results = []
    for art in root.findall(".//PubmedArticle"):
        pmid = art.findtext(".//PMID") or ""
        title = art.findtext(".//ArticleTitle") or ""
        abstract_texts = []
        for ab in art.findall(".//AbstractText"):
            label = ab.get("Label")
            section = (label + ": " if label else "") + (ab.text or "")
            abstract_texts.append(section)
        abstract = "\n".join(abstract_texts) if abstract_texts else "（要約なし）"
        journal = art.findtext(".//Journal/Title") or ""
        year = art.findtext(".//Journal/JournalIssue/PubDate/Year") or ""
        results.append({"pmid": pmid, "title": title, "abstract": abstract, "journal": journal, "year": year})
    return results

def summarize_with_gpt(text):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "あなたは医学に詳しいアシスタントです。"},
            {"role": "user", "content": f"次のPubMed要約を日本語でわかりやすく解説してください:\n\n{text}"}
        ],
        temperature=0.3
    )
    return response.choices[0].message["content"]

st.set_page_config(page_title="PubMed Chat検索", page_icon="🔎")
st.title("🔎 PubMed Chat検索サービス")

tab1, tab2 = st.tabs(["検索モード", "チャットモード"])

with tab1:
    st.subheader("PubMedを検索して要約を見る")
    term = st.text_input("検索キーワード", "diabetes")
    retmax = st.slider("取得件数", 1, 10, 5)

    if st.button("検索実行"):
        pmids = esearch(term, retmax)
        if not pmids:
            st.warning("検索結果が見つかりませんでした。")
        else:
            papers = efetch(pmids)
            for p in papers:
                with st.expander(f"{p['title'][:60]}..."):
                    st.markdown(f"**タイトル:** {p['title']}")
                    st.markdown(f"**ジャーナル・年:** {p['journal']}（{p['year']}）")
                    st.markdown(f"[PubMedで開く](https://pubmed.ncbi.nlm.nih.gov/{p['pmid']}/)")
                    st.markdown(f"**要約（原文）:**\n{p['abstract']}")
                    with st.spinner("GPTが解説中..."):
                        summary = summarize_with_gpt(p["abstract"])
                        st.success("**AIによる解説:**")
                        st.write(summary)

with tab2:
    st.subheader("チャットでPubMed検索")
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.write(m["content"])

    user_input = st.chat_input("検索したいことを入力してください")
    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("assistant"):
            st.write("検索中です…")
            pmids = esearch(user_input, 3)
            papers = efetch(pmids)
            if not papers:
                reply = "検索結果が見つかりませんでした。"
                st.write(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})
            else:
                summaries = []
                for p in papers:
                    text = f"{p['title']}（{p['journal']} {p['year']}）\n{p['abstract']}"
                    ai_summary = summarize_with_gpt(text)
                    summaries.append(f"- {p['title']} ({p['journal']} {p['year']})\n  {ai_summary}")
                reply = "\n\n".join(summaries)
                st.write(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})
