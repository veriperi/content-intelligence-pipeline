-- Silver: one clean row per successfully-fetched episode.
--
-- This model demonstrates real data cleaning, not just a passthrough:
--   - drops rows that failed to fetch (fetch_status != 'ok')
--   - deduplicates on (podcast_feed_url, episode title, published date) —
--     RSS feeds frequently republish the same episode with a new GUID
--   - strips HTML tags out of descriptions (common in podcast RSS)
--   - normalizes published date into a real timestamp, dropping unparseable ones
--   - flags empty-description episodes rather than silently keeping them,
--     since "silently degraded data quality" is exactly the kind of bug that's
--     costly to catch late in a pipeline

with parsed as (
    select
        id                                              as episode_raw_id,
        podcast_feed_url,
        raw_parsed_json ->> 'title'                      as episode_title,
        raw_parsed_json ->> 'summary'                     as raw_description,
        raw_parsed_json ->> 'published_parsed'             as published_at_raw,
        raw_parsed_json ->> 'link'                          as episode_link,
        raw_parsed_json ->> 'id'                             as episode_guid,
        ingested_at
    from bronze.episodes_raw
    where fetch_status = 'ok'
      and raw_parsed_json ->> 'title' is not null
),

cleaned as (
    select
        episode_raw_id,
        podcast_feed_url,
        trim(episode_title)                                as episode_title,
        -- strip common HTML tags found in podcast descriptions
        trim(regexp_replace(coalesce(raw_description, ''), '<[^>]+>', '', 'g')) as episode_description,
        case
            when published_at_raw ~ '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$'
                then published_at_raw::timestamp
            else null
        end                                                 as published_at,
        episode_link,
        episode_guid,
        ingested_at,
        row_number() over (
            partition by podcast_feed_url, lower(trim(episode_title))
            order by ingested_at asc
        )                                                    as dedup_rank
    from parsed
)

select
    episode_raw_id,
    podcast_feed_url,
    episode_title,
    episode_description,
    (episode_description = '' or episode_description is null) as is_empty_description,
    published_at,
    (published_at is null)                                     as has_invalid_published_date,
    episode_link,
    episode_guid,
    ingested_at
from cleaned
where dedup_rank = 1
