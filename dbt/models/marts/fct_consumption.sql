select
    reading_id,
    meter_id,
    reading_date,
    counter_liters,
    previous_counter_liters,
    interval_days,
    run_id,
    case
        when previous_counter_liters is null then 'initial'
        when counter_liters < previous_counter_liters then 'counter_reset'
        when interval_days <> 1 then 'gap'
        else 'valid'
    end as interval_status,
    case
        when interval_days = 1 and counter_liters >= previous_counter_liters
        then counter_liters - previous_counter_liters
        else null
    end as consumption_liters
from {{ ref('stg_readings') }}
