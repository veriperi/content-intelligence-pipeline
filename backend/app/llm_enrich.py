"""
GenAI enrichment layer.

Takes a raw episode (bronze.episodes_raw) and asks an LLM to:
  - categorize the content (topic/genre)
  - extract key entities (people, companies, products mentioned)
  - flag data-quality issues (empty description, likely-duplicate title,
    suspicious/placeholder text, non-English content, etc.)
  - assign a content_quality_score (0-100) with a short reason

The LLM call and its raw response are stored untouched in
bronze.llm_enrichment_raw. Nothing here writes to silver/gold — that
transformation happens in dbt, which is what gives you a clean story about
*why* the architecture is laid out the way it is when someone interviews you.
"""
import json
import time
import logging
from openai import OpenAI
from sqlalchemy import text as sql_text

from app.config import settings
from app.db import get_conn, insert_llm_enrichment_raw

logger = logging.getLogger("llm_enrich")
client = OpenAI(api_key=settings.OPENAI_API_KEY, base_url=settings.OPENAI_BASE_URL)



SYSTEM_PROMPT = """You are a content data-quality and categorization assistant for a
podcast analytics platform. Given a single podcast episode's raw title and
description, respond ONLY with a JSON object (no markdown, no preamble) with
this exact shape:

{
  "category": "one of: Technology, Business, True Crime, Comedy, News, Health, Education, Society & Culture, Sports, Arts, Other",
  "entities": ["list of notable people, companies, or products mentioned, max 5"],
  "quality_flags": ["list from: empty_description, placeholder_text, non_english, duplicate_suspected, excessive_length, promotional_only, none"],
  "quality_score": <integer 0-100, where 100 = rich, clean, well-formed metadata>,
  "quality_reason": "one short sentence explaining the score"
}
"""


def build_user_prompt(title: str, description: str) -> str:
    # Truncate to keep token usage predictable and cost bounded
    description = (description or "")[:1500]
    return f"Title: {title}\n\nDescription: {description}"


def enrich_episode(episode_raw_id: int, title: str, description: str) -> dict:
    """Call the LLM for one episode, store the raw response, return parsed result."""
    user_prompt = build_user_prompt(title, description)
    request_payload = {
        "model": settings.OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
    }

    start = time.time()
    response = client.chat.completions.create(**request_payload)
    latency_ms = int((time.time() - start) * 1000)

    raw_text = response.choices[0].message.content
    response_payload = {
        "raw_text": raw_text,
        "usage": response.usage.model_dump() if response.usage else None,
    }

    with get_conn() as conn:
        insert_llm_enrichment_raw(
            conn,
            episode_raw_id=episode_raw_id,
            model=settings.OPENAI_MODEL,
            prompt_version=settings.PROMPT_VERSION,
            request_payload=request_payload,
            response_payload=response_payload,
            latency_ms=latency_ms,
        )

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        logger.warning("Non-JSON LLM response for episode_raw_id=%s", episode_raw_id)
        parsed = {"parse_error": True, "raw_text": raw_text}

    return parsed


def enrich_pending_episodes(batch_size: int = 50) -> dict:
    """
    Find episodes in bronze that haven't been enriched yet and run them
    through the LLM. This is the second task in the Airflow DAG, run after
    ingestion.
    """
    query = sql_text(
        """
        SELECT e.id, e.raw_parsed_json
        FROM bronze.episodes_raw e
        LEFT JOIN bronze.llm_enrichment_raw l ON l.episode_raw_id = e.id
        WHERE e.fetch_status = 'ok'
          AND l.id IS NULL
        LIMIT :batch_size
        """
    )
    with get_conn() as conn:
        rows = conn.execute(query, {"batch_size": batch_size}).fetchall()

    processed, failed = 0, 0
    for row in rows:
        episode_id, raw_json = row[0], row[1]
        title = (raw_json or {}).get("title", "")
        description = (raw_json or {}).get("summary", "")
        try:
            enrich_episode(episode_id, title, description)
            processed += 1
        except Exception as e:
            logger.error("Enrichment failed for episode_raw_id=%s: %s", episode_id, e)
            failed += 1

    return {"processed": processed, "failed": failed, "batch_size": batch_size}


if __name__ == "__main__":
    print(enrich_pending_episodes(batch_size=10))
