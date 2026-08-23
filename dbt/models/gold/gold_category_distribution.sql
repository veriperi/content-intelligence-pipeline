-- Gold: how content is distributed across LLM-assigned categories,
-- compared against the publisher-declared genre from iTunes. Useful for
-- spotting mis-tagged content — e.g. a podcast tagged "Comedy" on iTunes
-- that the LLM consistently categorizes as "True Crime" based on actual
-- episode content is a genuinely interesting, demoable insight.

select
    p.genre                as source_declared_genre,
    en.category             as llm_assigned_category,
    count(*)                 as episode_count,
    round(avg(en.quality_score), 1) as avg_quality_score
from {{ ref('silver_episodes') }} e
join {{ ref('silver_podcasts') }} p
    on p.feed_url = e.podcast_feed_url
join {{ ref('silver_episode_enrichment') }} en
    on en.episode_raw_id = e.episode_raw_id
where en.category is not null
group by 1, 2
order by episode_count desc
