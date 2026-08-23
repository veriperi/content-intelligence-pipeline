-- Gold: aggregates content quality by publisher — a "which feeds need
-- attention" leaderboard, directly analogous to feed-health monitoring
-- work in a real content/media data platform.

select
    p.publisher,
    p.podcast_title,
    p.genre,
    count(distinct e.episode_raw_id)                          as episodes_analyzed,
    round(avg(en.quality_score), 1)                            as avg_quality_score,
    sum(case when e.is_empty_description then 1 else 0 end)    as episodes_missing_description,
    round(
        100.0 * sum(case when e.is_empty_description then 1 else 0 end)
        / nullif(count(distinct e.episode_raw_id), 0), 1
    )                                                            as pct_missing_description
from {{ ref('silver_podcasts') }} p
join {{ ref('silver_episodes') }} e
    on e.podcast_feed_url = p.feed_url
left join {{ ref('silver_episode_enrichment') }} en
    on en.episode_raw_id = e.episode_raw_id
group by 1, 2, 3
order by avg_quality_score asc nulls last
