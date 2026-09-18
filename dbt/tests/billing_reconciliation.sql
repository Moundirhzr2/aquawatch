select * from {{ ref('fct_billing') }}
where billed_amount_cents - expected_amount_cents <> signed_difference_cents
   or review_amount_cents < 0
   or (abs(signed_difference_cents) > 1 and review_amount_cents <> abs(signed_difference_cents))
