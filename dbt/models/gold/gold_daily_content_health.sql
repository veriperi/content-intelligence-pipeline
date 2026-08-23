-- Gold: one row per ingestion day, summarizing pipeline volume and data
-- quality — the metrics a "feed health" dashboard actually needs.

select
    date_trunc('day', e.ingested_at)                       as ingestion_date,
    count(*)                                                 as episodes_ingested,
    sum(case when e.is_empty_description then 1 else 0 end) as episodes_missing_description,
    sum(case when e.has_invalid_published_date then 1 else 0 end) as episodes_bad_date,
    round(
        100.0 * sum(case when en.llm_parse_failed then 1 else 0 end)
        / nullif(count(*), 0), 2
    )                                                          as llm_parse_failure_rate_pct,
    round(avg(en.quality_score), 1)                            as avg_quality_score,
    round(avg(en.latency_ms), 0)                                as avg_llm_latency_ms
from {{ ref('silver_episodes') }} e
left join {{ ref('silver_episode_enrichment') }} en
    on en.episode_raw_id = e.episode_raw_id
group by 1
order by 1 desc
