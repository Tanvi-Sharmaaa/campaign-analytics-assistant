import streamlit as st
import time
from langchain_groq import ChatGroq
from langchain_community.chat_message_histories import ChatMessageHistory
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os, re, time
import pandas as pd
import numpy as np
from io import BytesIO
from datetime import datetime, timedelta
import json
from prompts import insight_prompt,sql_generation_prompt,explain_result_prompt

# =========================
# CONFIG
# =========================
st.set_page_config(
    page_title="Voylla DesignGPT - Executive Dashboard",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Model configuration
MODEL_NAME = "gpt-4.1-mini"
LLM_TEMPERATURE = 0.1

# =========================
# KEYS & CONNECTIONS
# =========================
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error("🔑 No OpenAI key found – please add it to your app Secrets or .env")
    st.stop()

os.environ["OPENAI_API_KEY"] = api_key

@st.cache_resource
def get_llm():
    return ChatOpenAI(model=MODEL_NAME, temperature=LLM_TEMPERATURE, request_timeout=120, max_retries=3)

llm = get_llm()

@st.cache_resource
def get_engine_and_schema():
    """Create engine and return schema string for the single allowed table."""
    try:
        db_host = os.getenv("DB_HOST")
        db_port = os.getenv("DB_PORT")
        db_name = os.getenv("DB_NAME")
        db_user = os.getenv("DB_USER")
        db_password = os.getenv("DB_PASSWORD")
    except KeyError:
        st.error("❌ Missing DB_* secrets. Please add DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD.")
        st.stop()

    engine = create_engine(
        f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}",
        pool_pre_ping=True, pool_recycle=3600, pool_size=5, max_overflow=10
    )

    return engine

engine = get_engine_and_schema()
#print(engine)

# ========================= Brand options
@st.cache_data
def load_Brands():
    
    query = """
        SELECT DISTINCT "Brand"
        from blinkit_ads_data
        WHERE "Brand" IS NOT NULL
        ORDER BY "Brand";
    """
    df = pd.read_sql(query, engine)
    return df["Brand"].tolist()

Brands = load_Brands()

#========================   
@st.cache_data(ttl=300)
def ask_llm(prompt):
    return llm.invoke(prompt).content


# ---------------- DATE FILTER ----------------
col1, col2, col3 = st.columns(3)
with col1:
    start_date = st.date_input("Start Date")
with col2:
    end_date = st.date_input("End Date")
with col3:
    selected_Brand = st.selectbox("Select Brand",options=["All"] + Brands)

# ---------------- QUERY ----------------
indicator_query = """
SELECT
    SUM(direct_quantities_sold) AS direct_qty,
    SUM(indirect_quantities_sold) AS indirect_qty,
    SUM(estimated_budget_consumed) AS spend,
    SUM(direct_sales) AS direct_sales,
    SUM(indirect_sales) AS indirect_sales
from voylla.voylla_blinkit_ads_data
WHERE date BETWEEN %(start)s AND %(end)s;
"""

indicator_df = pd.read_sql(
    indicator_query,
    engine,
    params={"start": start_date, "end": end_date}
)
#print(indicator_df)
# ---------------- Indicator CARDS ----------------
i1, i2, i3, i4, i5 = st.columns(5)

i1.metric(label="Direct Qty Sold", value=int(indicator_df.direct_qty[0] or 0))
i2.metric("Indirect Qty Sold", int(indicator_df.indirect_qty[0] or 0))
i3.metric("Total Spend", f"₹{indicator_df.spend[0] or 0:,.0f}")
i4.metric("Direct Sales", f"₹{indicator_df.direct_sales[0] or 0:,.0f}")
i5.metric("Indirect Sales", f"₹{indicator_df.indirect_sales[0] or 0:,.0f}")


# =========================
st.subheader("Campaign Performance Overview")

left_col, right_col = st.columns([2, 1])  # left wider

with left_col:


    # ---------------- TOP 5 CAMPAIGNS ----------------
    st.markdown(
        "<h3 style='color:#2E7D32;'>🏆 Best Performing Campaigns</h3>",
        unsafe_allow_html=True
    )

    best_query = """
    SELECT
        campaign_name AS NAME,
        SUM(estimated_budget_consumed) AS SPEND,
        SUM(direct_sales + indirect_sales) AS SALES,
        --ROUND( SUM(estimated_budget_consumed)/SUM(direct_sales + indirect_sales), 2) AS ROAS
        ROUND( SUM(direct_sales + indirect_sales)/SUM(estimated_budget_consumed), 2) AS ROAS
    FROM voylla.voylla_blinkit_ads_data
    WHERE date BETWEEN %(start)s AND %(end)s
    GROUP BY campaign_name
    HAVING SUM(estimated_budget_consumed) > 0
    ORDER BY roas DESC
    LIMIT 5;
    """

    best_df = pd.read_sql(
        best_query,
        engine,
        params={"start": start_date, "end": end_date}
    )

    st.dataframe(best_df)

    # ---------------- WORST 5 CAMPAIGNS ----------------
    
    st.markdown(
        "<h3 style='color:#E53935;'>📉 Need Attention</h3>",
        unsafe_allow_html=True
    )
    worst_query = """
    SELECT
        campaign_name AS NAME,
        SUM(estimated_budget_consumed) AS SPEND,
        SUM(direct_sales + indirect_sales) AS SALES,
        ROUND( SUM(direct_sales + indirect_sales)/SUM(estimated_budget_consumed), 2) AS ROAS
        -- ROUND(AVG(total_ro_as), 2) AS ROAS
    FROM voylla.voylla_blinkit_ads_data
    WHERE date BETWEEN %(start)s AND %(end)s
    GROUP BY campaign_name
    HAVING SUM(estimated_budget_consumed) > 0
    ORDER BY roas ASC
    LIMIT 5;
    """
    worst_df = pd.read_sql(
        worst_query,
        engine,
        params={"start": start_date, "end": end_date}   
    )
    st.dataframe(worst_df)

with right_col:
    summary_payload = {
    "date_range": f"{start_date} to {end_date}",
    "best_campaigns": best_df.to_dict(orient="records"),
    "worst_campaigns": worst_df.to_dict(orient="records"),
    "Direct Sales": f"₹{indicator_df.direct_sales[0] or 0:,.0f}",
    "Indirect Sales": f"₹{indicator_df.indirect_sales[0] or 0:,.0f}",
    "total_spend": f"₹{indicator_df.spend[0] or 0:,.0f}"
    }

    st.markdown("###  Key Insights")


    with st.spinner("Analyzing performance..."):
        prompt=insight_prompt(summary_payload)
        insights = ask_llm(prompt) #cache this

    st.markdown(
        f"""
        <div style="
            height: 400px;
            overflow-y: auto;
            padding: 14px;
            border-radius: 10px;
            border: 1px solid #e5e7eb;
        ">
        {insights}
        </div>
        """,
        unsafe_allow_html=True
    )


# =========================

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


#============================

DB_SCHEMA = """
Table: voylla.voylla_blinkit_ads_data

Columns:
- id (int) — unique row id
- Brand (text) — Brand name
- date (date) — date of the record
- campaign_name (text)
- targeting_type (text)
- targeting_value (text)
- match_type (text)
- most_viewed_position (text)
- pacing_type (text)

Performance metrics:
- impressions (int)
- cpm (numeric)
- estimated_budget_consumed (numeric)

Conversions:
- direct_atc (int)
- indirect_atc (int)
- direct_quantities_sold (int)
- indirect_quantities_sold (int)

Revenue:
- direct_sales (numeric)
- indirect_sales (numeric)

ROI metrics:
- direct_ro_as (numeric)
- total_ro_as (numeric)

"""

def format_chat_history(history):
    lines = []
    for h in history[-5:]:
        lines.append(f"User: {h['user']}")
        lines.append(f"Assistant: {h['answer']}")
    return "\n".join(lines)
chat_context = format_chat_history(st.session_state.chat_history)

# =========================***************

FORBIDDEN = ["insert", "update", "delete", "drop", "alter", "truncate"]

def validate_sql(sql: str):
    sql_l = sql.lower()
    if not sql_l.startswith("select"):
        raise ValueError("Only SELECT queries allowed")

    if any(word in sql_l for word in FORBIDDEN):
        raise ValueError("Unsafe SQL detected")
    
def clean_sql(sql: str) -> str:
    sql = sql.strip()

    # Remove markdown fences
    if sql.startswith("```"):
        sql = sql.replace("```sql", "").replace("```", "").strip()

    # Ensure SELECT starts the query
    lower_sql = sql.lower()
    if "select" in lower_sql:
        sql = sql[lower_sql.find("select"):]

    return sql



PREDEFINED_QUESTIONS = [
    "Sales report for last month",
    "Top 5 campaigns by ROAS",
    "Worst performing campaigns",
    "Spend vs sales trend",
    "Which campaign needs attention"
]

def handle_question(question: str):
    with st.spinner("🔍 Analyzing data and generating insights..."):
        try:
            chat_context = [
                {"role": "user", "content": c["user"]}
                for c in st.session_state.chat_history
            ]

            sql_prompt = sql_generation_prompt(
                question,
                chat_context,
                DB_SCHEMA,
            )

            sql_query = clean_sql(llm.invoke(sql_prompt).content)
            validate_sql(sql_query)

            df = pd.read_sql(sql_query, engine)

            explain_prompt = explain_result_prompt(question, df)
            answer = ask_llm(explain_prompt)

            st.session_state.chat_history.append({
                "user": question,
                "last_sql": sql_query,
                "answer": answer
            })

            st.session_state.chat_history = st.session_state.chat_history[-5:]
            st.session_state.last_sql = sql_query
            st.rerun()

        except Exception as e:
            st.error(f"❌ Analysis Error: {str(e)}")



st.divider()
st.subheader("🤖 Ask Me Anything")
left_col, right_col = st.columns([2, 1])  # left wider
final_question = None

with left_col:

    chat_container = st.container(height=220)

    with chat_container:
        if st.session_state.chat_history:
            for chat in st.session_state.chat_history:
                st.markdown(f"**🧑 You:** {chat['user']}")
                st.markdown(f"**🤖 Assistant:** {chat['answer']}")
                st.divider()
        else:
            st.info("Ask a question to get started 👇")

    user_question = st.text_input(
        "Ask a question about campaign performance",
        placeholder="e.g. Sales in Feb"
    )

    ask_btn = st.button("🚀 Ask", use_container_width=True)

    if ask_btn and user_question.strip():
        final_question = user_question

with right_col:
    st.subheader("💡 Quick Questions")

    for q in PREDEFINED_QUESTIONS:
        if st.button(q):
            final_question = q

if final_question:
    handle_question(final_question)

if "last_sql" in st.session_state:
    with st.expander("🔍 Generated SQL"): 
        st.code(st.session_state.last_sql, language="sql")

