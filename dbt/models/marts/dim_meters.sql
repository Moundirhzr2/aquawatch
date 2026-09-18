select
    m.id as meter_id,
    c.id as customer_id,
    c.name as customer_name,
    c.district,
    c.segment,
    cast(m.installed_on as date) as installed_on
from {{ operational('meters') }} m
inner join {{ operational('customers') }} c on c.id = m.customer_id
