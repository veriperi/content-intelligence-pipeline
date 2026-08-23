-- Silver: parses the LLM's raw JSON text response into real typed columns.
--
-- Design note: the LLM's response is stored as raw text in bronze
-- (response_payload ->> 'raw_text') because it isn't guaranteed to be valid
-- JSON on every call. Here we defensively parse it and simply drop rows
-- that fail — visible as a gap between silver_episodes and this model's
-- row count, which is itself a useful data-quality metric to show in the
-- gold-layer dashboard (LLM parse success rate).

with latest_enrichment as (
    select
        episode_raw_id,
        response_payload ->> 'raw_text' as raw_text,
        model,
        prompt_version,
        latency_ms,
        ingested_at,
        row_number() over (
            partition by episode_raw_id
            order by ingested_at desc
        ) as rn
    from bronze.llm_enrichment_raw
),

parsed as (
    select
        episode_raw_id,
        model,
        prompt_version,
        latency_ms,
        ingested_at as enriched_at,
        raw_text,
        -- Postgres will raise on invalid JSON, so we guard with a regex
        -- sanity check first rather than relying on try/catch (dbt/Postgres
        -- SQL doesn't have one natively without a plpgsql function).
        case when raw_text ~ '^\s*\{' then raw_text::jsonb else null end as response_json
    from latest_enrichment
    where rn = 1
)

select
    episode_raw_id,
    model,
    prompt_version,
    latency_ms,
    enriched_at,
    response_json ->> 'category'                                       as category,
    (response_json -> 'entities')::text                                as entities_json,
    (response_json -> 'quality_flags')::text                           as quality_flags_json,
    nullif(response_json ->> 'quality_score', '')::int                 as quality_score,
    response_json ->> 'quality_reason'                                  as quality_reason,
    (response_json is null)                                             as llm_parse_failed
from parsed
