select
    id as run_id,
    file_name,
    cast(started_at as timestamp) as started_at,
    status,
    accepted,
    rejected,
    duplicates
from {{ operational('ingestion_runs') }}
