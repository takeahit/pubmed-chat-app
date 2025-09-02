import requests
import xml.etree.ElementTree as ET
import streamlit as st
from openai import OpenAI

# --- Secrets ---
PUBMED_API_KEY = st.secrets["PUBMED_API_KEY"]
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
client = OpenAI(api_key=OPENAI_API_KEY)

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"

# ====== 1) 日本語→英語PubMed検索式 変換 ======
@st.cache_data(ttl=3600)
def jp_to_pubmed_query(jp_text: str) -> str:
    """
    日本語の自然文を、英語のPubMed検索式(Boolean/MeSH含む)に要約変換する。
    例）糖尿病の合併症をSGLT2で… → (diabetes mellitus[MeSH Terms] OR diabetes[tiab]) AND (SGLT2 inhibitors[MeSH Terms] OR SGLT2[tiab])
    """
    prompt = f"""
あなたはPubMedの検索式を作る専門家です。
次の日本語要望から、英語のPubMed検索式を1行で作ってください。
- できれば MeSH Terms と tiab を併用
- AND/OR/() を適切に
- 範囲指示（年など）があれば english の pubdate フィルタも例示（例：("2021"[Date - Publication] : "3000"[Date - Publication])）
- 出力は式のみ、余計な説明は書かない

日本語要望:
{jp_text}
"""
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )
    query = resp.choices[0].message.content.strip()
    # 万一バッククォートなどで返ってきたら除去
    return query.replace("`", "").replace("\n", " ").strip()

# ====== 2) PubMed検索（E-utilities） ======
@st.cache_data(ttl=120)
def esearch(term: str, retmax: int = 10):
    params = {"db": "pubmed", "term": term, "retmax": retmax, "retmode": "json", "api_key": PUBMED_API_KEY}
    r = requests.get(BASE + "esearch.fcgi", params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data.get("esearchresult", {}).get("idlist", [])

@st.cache_data(ttl=120)
def efetch(pmids):
    if not pmids: return []
    params = {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml", "api_key": PUBMED_API_KEY}
    r = requests.get(BASE + "efetch.fcgi", params=params, timeout=60)
    r.raise_for_status()
    root = ET.fromstring(r.text)
    out = []
    for art in root.findall(".//PubmedArticle"):
        pmid = art.findtext(".//PMID") or ""
        title = art.findtext(".//ArticleTitle") or ""
        abs_parts = []
        for ab in art.findall(".//AbstractText"):
            label = ab.get("Label")
            section = (label + ": " if label else "") + (ab.text or "")
            abs_parts.append(section)
        abstract = "\n".join(abs_parts) if abs_parts else "（要約なし）"
        journal = art.findtext(".//Journal/Title") or ""
        year = art.findtext(".//Journal/JournalIssue/PubDate/Year") or ""
        out.append({"pmid": pmid, "title": title, "abstract": abstract, "journal": journal, "year": year})
    return out

# ====== 3) 英文要約のやさしい日本語解説 ======
def summarize_with_gpt(text):
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "あなたは医学に詳しく、簡潔で正確な日本語要約が得意です。"},
            {"role": "user", "content": f"次のPubMed抄録を日本語で、臨床家向けに3～5行で要約してください。\n\n{text}"}
        ],
        temperature=0.3
    )
    return resp.choices[0].message.content

# ====== UI ======
st.set_page_config(page_title="PubMed 日本語→英語変換検索＋チャット", page_icon="🔎")
st.title("🔎 PubMed 日本語→英語変換検索＋チャット")

tab1, tab2 = st.tabs(["検索モード", "チャットモード"])

# ---- 検索モード ----
with tab1:
    st.subheader("日本語の自然文で検索できます")
    jp = st.text_area("日本語で書いてください（例：『2型糖尿病でSGLT2阻害薬の腎アウトカム 2021年以降』など）", "SGLT2阻害薬による2型糖尿病患者の腎臓アウトカム 2021年以降")
    retmax = st.slider("取得件数", 1, 20, 5)
    if st.button("検索を実行"):
        with st.spinner("日本語 → 英語の検索式を作成中…"):
            en_query = jp_to_pubmed_query(jp)
        st.caption("英語検索式（編集可）")
        en_query = st.text_area("Generated PubMed query", en_query, height=80)
        with st.spinner("PubMedを検索中…"):
            pmids = esearch(en_query, retmax)
        if not pmids:
            st.warning("該当なしでした。検索式を少し簡単にして再実行してみてください。")
        else:
            papers = efetch(pmids)
            for p in papers:
                with st.expander(f"{p['title'][:60]}..."):
                    st.markdown(f"**タイトル**: {p['title']}")
                    st.markdown(f"**ジャーナル・年**: {p['journal']}（{p['year']}）")
                    st.markdown(f"[PubMedで開く](https://pubmed.ncbi.nlm.nih.gov/{p['pmid']}/)")
                    st.markdown(f"**要約（原文）**:\n{p['abstract']}")
                    with st.spinner("AIが日本語で要約中…"):
                        st.success(summarize_with_gpt(p["abstract"]))

# ---- チャットモード ----
with tab2:
    st.subheader("自然文で質問 → 検索式に自動変換 → 文献要約を返答")
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.write(m["content"])

    jp_input = st.chat_input("例：『心不全でSGLT2の入院抑制効果 2022年以降』など")
    if jp_input:
        st.session_state.messages.append({"role": "user", "content": jp_input})
        with st.chat_message("assistant"):
            with st.spinner("日本語→英語検索式を生成中…"):
                en_query = jp_to_pubmed_query(jp_input)
            st.write("生成した検索式：")
            st.code(en_query)

            with st.spinner("PubMed検索中…"):
                pmids = esearch(en_query, 5)
                papers = efetch(pmids)

            if not papers:
                reply = "文献が見つかりませんでした。検索式を少し緩めてみてください。"
                st.write(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})
            else:
                lines = []
                for p in papers:
                    jp_sum = summarize_with_gpt(f"{p['title']} ({p['journal']} {p['year']})\n{p['abstract']}")
                    lines.append(f"- **{p['title']}**（{p['journal']} {p['year']}）PMID:{p['pmid']}\n  {jp_sum}")
                reply = "\n\n".join(lines)
                st.write(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})
