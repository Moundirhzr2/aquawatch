select * from {{ ref('fct_consumption') }}
where (interval_status = 'valid' and (consumption_liters is null or consumption_liters < 0))
   or (interval_status <> 'valid' and consumption_liters is not null)
