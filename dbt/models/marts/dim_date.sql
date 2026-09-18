select distinct
    reading_date as calendar_date,
    extract(year from reading_date) as year_number,
    extract(month from reading_date) as month_number,
    extract(day from reading_date) as day_number
from {{ ref('fct_consumption') }}
