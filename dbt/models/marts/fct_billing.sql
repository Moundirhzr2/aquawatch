with meter_evidence as (
    select
        i.id as invoice_id,
        max(case when c.reading_date = cast(i.period_start as date)
            then c.counter_liters end) as start_counter_liters,
        max(case when c.reading_date = cast(i.period_end as date)
            then c.counter_liters end) as end_counter_liters,
        coalesce(sum(case when c.reading_date > cast(i.period_start as date)
            and c.interval_days > 1 then c.interval_days - 1 else 0 end), 0) as missing_days,
        coalesce(sum(case when c.reading_date > cast(i.period_start as date)
            and c.counter_liters < c.previous_counter_liters then 1 else 0 end), 0) as reset_events
    from {{ operational('invoices') }} i
    left join {{ ref('fct_consumption') }} c
        on c.meter_id = i.meter_id
        and c.reading_date between cast(i.period_start as date) and cast(i.period_end as date)
    group by i.id
), calculated as (
    select
        i.id as invoice_id,
        i.meter_id,
        i.tariff_id,
        cast(i.period_start as date) as period_start,
        cast(i.period_end as date) as period_end,
        i.billed_volume_liters,
        i.billed_amount_cents,
        cast(floor((cast(i.billed_volume_liters as bigint) * t.rate_cents_per_m3 + 500) / 1000.0) as bigint)
            + t.fixed_fee_cents as expected_amount_cents,
        e.start_counter_liters,
        e.end_counter_liters,
        case when e.start_counter_liters is null or e.end_counter_liters is null
            then 0 else e.missing_days end as missing_days,
        case when e.start_counter_liters is null or e.end_counter_liters is null
            then 0 else e.reset_events end as reset_events,
        case
            when cast(i.period_end as date) <= cast(i.period_start as date) then 'invalid_period'
            when e.start_counter_liters is null or e.end_counter_liters is null then 'missing_boundary'
            when e.reset_events > 0 then 'counter_reset'
            when e.missing_days > 0 then 'incomplete'
            when abs(i.billed_volume_liters - (e.end_counter_liters - e.start_counter_liters)) > 1000
                then 'mismatch'
            else 'matched'
        end as volume_status
    from {{ operational('invoices') }} i
    inner join {{ operational('tariffs') }} t on t.id = i.tariff_id
    inner join meter_evidence e on e.invoice_id = i.id
), compared as (
    select *,
        case when volume_status in ('matched', 'mismatch')
            then end_counter_liters - start_counter_liters else null end as measured_volume_liters
    from calculated
)
select *,
    billed_amount_cents - expected_amount_cents as signed_difference_cents,
    case when abs(billed_amount_cents - expected_amount_cents) > 1
        then abs(billed_amount_cents - expected_amount_cents) else 0 end as review_amount_cents,
    case when measured_volume_liters is not null
        then billed_volume_liters - measured_volume_liters else null end as signed_volume_difference_liters,
    case when volume_status = 'mismatch'
        then abs(billed_volume_liters - measured_volume_liters) else 0 end as volume_review_liters
from compared
