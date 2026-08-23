"""
Content Intelligence Pipeline — Dashboard

Reads directly from the Gold layer tables (built by dbt) and renders them
as an interactive feed-health dashboard. This is deliberately a thin
presentation layer — all the real logic (cleaning, aggregation) already
happened in dbt. The dashboard's only job is to query and display.
"""
import os
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import plotly.express as px
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="Content Intelligence Pipeline",
    page_icon="🎙️",
    layout="wide",
)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/content_pipeline",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


@st.cache_data(ttl=60)
def run_query(sql: str) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql_query(text(sql), conn)


st.title("🎙️ Content Intelligence Pipeline")
st.caption("Podcast feed ingestion, LLM enrichment, and content quality monitoring")

# ---------------------------------------------------------------------------
# Top-level health metrics
# ---------------------------------------------------------------------------
try:
    health_df = run_query("SELECT * FROM public_gold.gold_daily_content_health ORDER BY ingestion_date DESC")
except Exception as e:
    st.error(f"Couldn't connect to the database. Is Postgres running? Details: {e}")
    st.stop()

if health_df.empty:
    st.warning("No data yet — run ingestion, enrichment, and `dbt run` first.")
    st.stop()

latest = health_df.iloc[0]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Episodes Ingested (latest day)", int(latest["episodes_ingested"]))
col2.metric("Avg Quality Score", f"{latest['avg_quality_score']:.1f}" if pd.notna(latest["avg_quality_score"]) else "—")
col3.metric("Missing Descriptions", int(latest["episodes_missing_description"]))
col4.metric("LLM Parse Failure Rate", f"{latest['llm_parse_failure_rate_pct']:.1f}%" if pd.notna(latest["llm_parse_failure_rate_pct"]) else "—")

st.divider()

# ---------------------------------------------------------------------------
# Category distribution + genre mismatch
# ---------------------------------------------------------------------------
st.subheader("📊 Content Category Distribution")
st.caption("Publisher-declared genre vs. LLM-assigned category, by episode count")

category_df = run_query("SELECT * FROM public_gold.gold_category_distribution ORDER BY episode_count DESC")

left, right = st.columns([2, 1])

with left:
    fig = px.bar(
        category_df,
        x="llm_assigned_category",
        y="episode_count",
        color="source_declared_genre",
        title="LLM-Assigned Category (colored by publisher's declared genre)",
        labels={"llm_assigned_category": "AI-Assigned Category", "episode_count": "Episodes", "source_declared_genre": "Publisher Genre"},
    )
    st.plotly_chart(fig, use_container_width=True)

with right:
    mismatch_pct = (
        100 * (category_df["source_declared_genre"] != category_df["llm_assigned_category"]).sum()
        / len(category_df)
    ) if len(category_df) else 0
    st.metric("Genre/Category Mismatch Rate", f"{mismatch_pct:.0f}% of rows")
    st.caption(
        "How often the LLM's content-based categorization disagrees with the "
        "publisher's own declared genre — a signal that publisher metadata "
        "alone isn't reliable for accurate content classification."
    )

st.dataframe(category_df, use_container_width=True, hide_index=True)

st.divider()

# ---------------------------------------------------------------------------
# Publisher quality leaderboard
# ---------------------------------------------------------------------------
st.subheader("🏆 Publisher Quality Leaderboard")
st.caption("Which feeds have the cleanest, highest-quality content")

publisher_df = run_query(
    "SELECT * FROM public_gold.gold_publisher_quality ORDER BY avg_quality_score DESC NULLS LAST"
)

fig2 = px.bar(
    publisher_df,
    x="publisher",
    y="avg_quality_score",
    color="avg_quality_score",
    color_continuous_scale="RdYlGn",
    title="Average Content Quality Score by Publisher",
    labels={"avg_quality_score": "Avg Quality Score", "publisher": "Publisher"},
)
st.plotly_chart(fig2, use_container_width=True)

st.dataframe(
    publisher_df[
        ["publisher", "podcast_title", "genre", "episodes_analyzed", "avg_quality_score", "pct_missing_description"]
    ],
    use_container_width=True,
    hide_index=True,
)

st.divider()
st.caption("Data refreshes every 60 seconds. Re-run `dbt run` after new ingestion to update the underlying tables.")