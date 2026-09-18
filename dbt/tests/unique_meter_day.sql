select meter_id, reading_date, count(*) as row_count
from {{ ref('fct_consumption') }}
group by meter_id, reading_date
having count(*) <> 1
