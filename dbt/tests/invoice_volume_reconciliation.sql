select * from {{ ref('fct_billing') }}
where volume_review_liters < 0
   or (volume_status = 'mismatch' and (
       measured_volume_liters is null
       or abs(signed_volume_difference_liters) <= 1000
       or volume_review_liters <> abs(signed_volume_difference_liters)
   ))
   or (volume_status = 'matched' and (
       measured_volume_liters is null
       or abs(signed_volume_difference_liters) > 1000
       or volume_review_liters <> 0
   ))
   or (volume_status not in ('matched', 'mismatch') and (
       measured_volume_liters is not null
       or signed_volume_difference_liters is not null
       or volume_review_liters <> 0
   ))
