with ordered as (
    select
        id as reading_id,
        meter_id,
        cast(reading_date as date) as reading_date,
        cast(counter_liters as bigint) as counter_liters,
        run_id,
        lag(cast(counter_liters as bigint)) over (
            partition by meter_id order by reading_date
        ) as previous_counter_liters,
        lag(cast(reading_date as date)) over (
            partition by meter_id order by reading_date
        ) as previous_date
    from {{ operational('readings') }}
)
select *,
    {{ dbt.datediff('previous_date', 'reading_date', 'day') }} as interval_days
from ordered
