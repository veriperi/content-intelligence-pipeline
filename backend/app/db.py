"""
Thin database helper. Uses SQLAlchemy core (not the full ORM) so the SQL
stays visible and debuggable — useful when you're describing your own
queries in an interview instead of hiding behind ORM magic.
"""
import json
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from app.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)


@contextmanager
def get_conn():
    conn = engine.connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def insert_podcast_raw(conn, source, query_term, itunes_id, feed_url, raw_json: dict):
    conn.execute(
        text(
            """
            INSERT INTO bronze.podcasts_raw (source, query_term, itunes_id, feed_url, raw_json)
            VALUES (:source, :query_term, :itunes_id, :feed_url, :raw_json)
            """
        ),
        {
            "source": source,
            "query_term": query_term,
            "itunes_id": itunes_id,
            "feed_url": feed_url,
            "raw_json": json.dumps(raw_json),
        },
    )


def insert_episode_raw(conn, podcast_feed_url, raw_xml_item, raw_parsed_json, fetch_status, fetch_error=None):
    result = conn.execute(
        text(
            """
            INSERT INTO bronze.episodes_raw
                (podcast_feed_url, raw_xml_item, raw_parsed_json, fetch_status, fetch_error)
            VALUES
                (:podcast_feed_url, :raw_xml_item, :raw_parsed_json, :fetch_status, :fetch_error)
            RETURNING id
            """
        ),
        {
            "podcast_feed_url": podcast_feed_url,
            "raw_xml_item": raw_xml_item,
            "raw_parsed_json": json.dumps(raw_parsed_json) if raw_parsed_json else None,
            "fetch_status": fetch_status,
            "fetch_error": fetch_error,
        },
    )
    return result.scalar_one()


def insert_llm_enrichment_raw(conn, episode_raw_id, model, prompt_version, request_payload, response_payload, latency_ms):
    conn.execute(
        text(
            """
            INSERT INTO bronze.llm_enrichment_raw
                (episode_raw_id, model, prompt_version, request_payload, response_payload, latency_ms)
            VALUES
                (:episode_raw_id, :model, :prompt_version, :request_payload, :response_payload, :latency_ms)
            """
        ),
        {
            "episode_raw_id": episode_raw_id,
            "model": model,
            "prompt_version": prompt_version,
            "request_payload": json.dumps(request_payload),
            "response_payload": json.dumps(response_payload),
            "latency_ms": latency_ms,
        },
    )
