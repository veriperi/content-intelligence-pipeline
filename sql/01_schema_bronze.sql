-- ============================================================
-- BRONZE LAYER
-- Raw, untouched data exactly as received from source APIs/feeds.
-- Never update or delete rows here — append only.
-- ============================================================

CREATE TABLE IF NOT EXISTS bronze.podcasts_raw (
    id                  SERIAL PRIMARY KEY,
    source              TEXT NOT NULL,             -- e.g. 'itunes_search'
    query_term          TEXT,                       -- search term used to discover this podcast
    itunes_id           BIGINT,
    feed_url            TEXT,
    raw_json            JSONB NOT NULL,              -- full untouched API response
    ingested_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bronze.episodes_raw (
    id                  SERIAL PRIMARY KEY,
    podcast_feed_url    TEXT NOT NULL,
    raw_xml_item        TEXT,                        -- raw <item> block from the RSS feed, as text
    raw_parsed_json     JSONB,                        -- feedparser's parsed dict, untouched
    fetch_status        TEXT,                         -- 'ok', 'http_error', 'parse_error'
    fetch_error         TEXT,
    ingested_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bronze.llm_enrichment_raw (
    id                  SERIAL PRIMARY KEY,
    episode_raw_id      INTEGER REFERENCES bronze.episodes_raw(id),
    model               TEXT NOT NULL,
    prompt_version      TEXT NOT NULL,
    request_payload     JSONB,
    response_payload    JSONB NOT NULL,               -- raw LLM response, untouched
    latency_ms          INTEGER,
    ingested_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_episodes_raw_feed_url ON bronze.episodes_raw(podcast_feed_url);
CREATE INDEX IF NOT EXISTS idx_llm_enrichment_episode ON bronze.llm_enrichment_raw(episode_raw_id);
