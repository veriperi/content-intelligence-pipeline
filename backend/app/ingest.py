"""
Ingestion layer — discovers podcasts and pulls their RSS feeds.

Two data sources, both free / no API key required:
  1. iTunes Search API  -> podcast-level discovery (title, feed URL, category, etc.)
  2. The podcast's own RSS feed -> episode-level data (messy, inconsistent, real-world)

Design note: this module writes ONLY to the bronze layer. It does not clean,
normalize, or validate anything — that's the job of the silver dbt models.
Keeping that boundary strict is the whole point of a bronze/silver/gold design,
and it's worth being able to explain that boundary clearly in an interview.
"""
import time
import logging
import requests
import feedparser

from app.config import settings
from app.db import get_conn, insert_podcast_raw, insert_episode_raw

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ingest")


def search_podcasts(term: str, limit: int = 20) -> list[dict]:
    """Query the iTunes Search API for podcasts matching a search term."""
    resp = requests.get(
        settings.ITUNES_SEARCH_URL,
        params={"term": term, "media": "podcast", "limit": limit},
        timeout=settings.REQUEST_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    return resp.json().get("results", [])


def ingest_podcasts_for_term(term: str, limit: int = 20) -> list[dict]:
    """Search + store podcast metadata in bronze. Returns the raw results."""
    results = search_podcasts(term, limit=limit)
    with get_conn() as conn:
        for r in results:
            insert_podcast_raw(
                conn,
                source="itunes_search",
                query_term=term,
                itunes_id=r.get("collectionId"),
                feed_url=r.get("feedUrl"),
                raw_json=r,
            )
    logger.info("Ingested %d podcasts for term=%r", len(results), term)
    return results


def ingest_episodes_for_feed(feed_url: str, max_episodes: int | None = None) -> dict:
    """
    Fetch a podcast's RSS feed and store each episode's raw entry in bronze.

    Real RSS feeds are inconsistent — missing descriptions, malformed dates,
    HTML-laden summaries, duplicate GUIDs. We do NOT try to fix any of that
    here; we store it as-is and record fetch_status so silver-layer dbt
    models can decide how to handle bad rows, and so data quality issues
    are traceable back to source rather than silently dropped.
    """
    max_episodes = max_episodes or settings.MAX_EPISODES_PER_FEED
    stored = 0
    errors = 0

    try:
        parsed = feedparser.parse(feed_url)
    except Exception as e:
        logger.warning("Failed to parse feed %s: %s", feed_url, e)
        with get_conn() as conn:
            insert_episode_raw(
                conn,
                podcast_feed_url=feed_url,
                raw_xml_item=None,
                raw_parsed_json=None,
                fetch_status="http_error",
                fetch_error=str(e),
            )
        return {"feed_url": feed_url, "stored": 0, "errors": 1}

    entries = parsed.entries[:max_episodes]

    with get_conn() as conn:
        for entry in entries:
            try:
                entry_dict = dict(entry)
                # feedparser struct_time objects aren't JSON serializable — normalize
                for k in ("published_parsed", "updated_parsed"):
                    if entry_dict.get(k):
                        entry_dict[k] = time.strftime("%Y-%m-%dT%H:%M:%S", entry_dict[k])

                insert_episode_raw(
                    conn,
                    podcast_feed_url=feed_url,
                    raw_xml_item=entry.get("summary", ""),
                    raw_parsed_json=entry_dict,
                    fetch_status="ok",
                )
                stored += 1
            except Exception as e:
                logger.warning("Failed to store episode from %s: %s", feed_url, e)
                insert_episode_raw(
                    conn,
                    podcast_feed_url=feed_url,
                    raw_xml_item=None,
                    raw_parsed_json=None,
                    fetch_status="parse_error",
                    fetch_error=str(e),
                )
                errors += 1

    logger.info("Feed %s: stored=%d errors=%d", feed_url, stored, errors)
    return {"feed_url": feed_url, "stored": stored, "errors": errors}


def run_full_ingestion(search_terms: list[str], podcasts_per_term: int = 10) -> dict:
    """End-to-end: search terms -> podcasts -> episodes. This is what the
    Airflow DAG calls as its first task."""
    summary = {"terms": {}, "feeds_processed": 0, "episodes_stored": 0}

    for term in search_terms:
        podcasts = ingest_podcasts_for_term(term, limit=podcasts_per_term)
        summary["terms"][term] = len(podcasts)

        for p in podcasts:
            feed_url = p.get("feedUrl")
            if not feed_url:
                continue
            result = ingest_episodes_for_feed(feed_url)
            summary["feeds_processed"] += 1
            summary["episodes_stored"] += result["stored"]

    return summary


if __name__ == "__main__":
    # Quick manual test: python -m app.ingest
    out = run_full_ingestion(["technology", "true crime", "startup"], podcasts_per_term=5)
    print(out)
