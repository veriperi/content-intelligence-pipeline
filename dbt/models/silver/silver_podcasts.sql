-- Silver: one clean row per podcast, deduplicated on feed_url, with
-- normalized fields pulled out of the raw JSON blob.
--
-- Design note: bronze.podcasts_raw can contain the same podcast multiple
-- times (re-ingested on different runs, or matched by more than one search
-- term). We take the most recently ingested row per feed_url as the source
-- of truth — a common real-world "slowly changing dimension, type 1" pattern.

with ranked as (
    select
        raw_json ->> 'collectionName'      as podcast_title,
        raw_json ->> 'artistName'           as publisher,
        raw_json ->> 'primaryGenreName'     as genre,
        feed_url,
        itunes_id,
        query_term,
        (raw_json ->> 'trackCount')::int    as episode_count_at_ingest,
        raw_json ->> 'artworkUrl600'        as artwork_url,
        raw_json ->> 'releaseDate'          as feed_last_release_date,
        ingested_at,
        row_number() over (
            partition by feed_url
            order by ingested_at desc
        ) as rn
    from bronze.podcasts_raw
    where feed_url is not null
      and trim(feed_url) != ''
)

select
    feed_url,
    itunes_id,
    query_term,
    trim(podcast_title)                        as podcast_title,
    trim(publisher)                             as publisher,
    coalesce(nullif(trim(genre), ''), 'Unknown') as genre,
    episode_count_at_ingest,
    artwork_url,
    feed_last_release_date::timestamptz         as feed_last_release_date,
    ingested_at                                  as first_seen_at
from ranked
where rn = 1
