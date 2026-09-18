select
    id as case_id,
    meter_id,
    kind,
    cast(event_date as date) as event_date,
    severity,
    status,
    amount_cents,
    version,
    title
from {{ operational('cases') }}
