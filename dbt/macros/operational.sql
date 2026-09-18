{% macro operational(table_name) -%}
  {%- if target.type == 'postgres' -%}
    {{ source('operational', table_name) }}
  {%- else -%}
    {{ ref('raw_' ~ table_name) }}
  {%- endif -%}
{%- endmacro %}
