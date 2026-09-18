with calculated as (
    select
        i.id as invoice_id,
        i.meter_id,
        i.tariff_id,
        cast(i.period_start as date) as period_start,
        cast(i.period_end as date) as period_end,
        i.billed_volume_liters,
        i.billed_amount_cents,
        cast(floor((cast(i.billed_volume_liters as bigint) * t.rate_cents_per_m3 + 500) / 1000.0) as bigint)
            + t.fixed_fee_cents as expected_amount_cents
    from {{ operational('invoices') }} i
    inner join {{ operational('tariffs') }} t on t.id = i.tariff_id
)
select *,
    billed_amount_cents - expected_amount_cents as signed_difference_cents,
    case when abs(billed_amount_cents - expected_amount_cents) > 1
        then abs(billed_amount_cents - expected_amount_cents) else 0 end as review_amount_cents
from calculated
