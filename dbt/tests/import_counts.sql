select * from {{ ref('fct_imports') }}
where accepted < 0 or rejected < 0 or duplicates < 0 or duplicates > rejected
