select
    reading_date,
    count(*) as received_readings,
    sum(case when interval_status = 'valid' then 1 else 0 end) as valid_intervals,
    sum(consumption_liters) as consumption_liters
from {{ ref('fct_consumption') }}
group by reading_date
