"""
FastAPI app. In production this would mostly be triggered by Airflow, not
by a human clicking buttons — but exposing these as endpoints makes local
testing and demoing (e.g. in an interview) much easier than only having a
CLI.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import text as sql_text

from app.db import get_conn
from app.ingest import ingest_podcasts_for_term, ingest_episodes_for_feed, run_full_ingestion
from app.llm_enrich import enrich_pending_episodes

app = FastAPI(
    title="Content Intelligence Pipeline API",
    description="Ingests podcast/feed data and enriches it with LLM-based categorization and quality scoring.",
    version="0.1.0",
)


class IngestTermRequest(BaseModel):
    term: str
    limit: int = 10


class IngestFeedRequest(BaseModel):
    feed_url: str


class FullIngestionRequest(BaseModel):
    search_terms: list[str]
    podcasts_per_term: int = 10


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ingest/podcasts")
def ingest_podcasts(req: IngestTermRequest):
    try:
        results = ingest_podcasts_for_term(req.term, limit=req.limit)
        return {"term": req.term, "podcasts_found": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingest/episodes")
def ingest_episodes(req: IngestFeedRequest):
    try:
        return ingest_episodes_for_feed(req.feed_url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingest/full")
def ingest_full(req: FullIngestionRequest):
    try:
        return run_full_ingestion(req.search_terms, podcasts_per_term=req.podcasts_per_term)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/enrich/pending")
def enrich_pending(batch_size: int = 50):
    try:
        return enrich_pending_episodes(batch_size=batch_size)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats/bronze")
def bronze_stats():
    """Quick sanity-check endpoint: row counts per bronze table."""
    with get_conn() as conn:
        podcasts = conn.execute(sql_text("SELECT count(*) FROM bronze.podcasts_raw")).scalar_one()
        episodes = conn.execute(sql_text("SELECT count(*) FROM bronze.episodes_raw")).scalar_one()
        enriched = conn.execute(sql_text("SELECT count(*) FROM bronze.llm_enrichment_raw")).scalar_one()
    return {"podcasts_raw": podcasts, "episodes_raw": episodes, "llm_enrichment_raw": enriched}
