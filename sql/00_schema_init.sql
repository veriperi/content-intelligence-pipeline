-- ============================================================
-- Run this first: creates the three schemas that separate
-- raw data, cleaned data, and business-ready aggregates.
-- ============================================================

CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;

-- Silver and Gold tables are NOT created here — they're built
-- by dbt models in dbt/models/silver and dbt/models/gold.
-- This keeps a clean separation: bronze = raw ingestion (SQL/Python),
-- silver+gold = transformation logic (dbt), which is exactly the
-- separation of concerns a data engineering interviewer will ask about.
