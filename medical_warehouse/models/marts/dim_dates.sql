-- models/marts/dim_dates.sql
-- Date dimension generated from a spine covering the full range of
-- message dates seen in staging (no dbt_utils dependency required).

with bounds as (

    select
        min(message_date)::date as min_date,
        max(message_date)::date as max_date
    from {{ ref('stg_telegram_messages') }}

),

date_spine as (

    select generate_series(
        (select min_date from bounds),
        (select max_date from bounds),
        interval '1 day'
    )::date as full_date

)

select
    to_char(full_date, 'YYYYMMDD')::int        as date_key,
    full_date,
    extract(dow from full_date)::int           as day_of_week,
    to_char(full_date, 'Day')                  as day_name,
    extract(week from full_date)::int          as week_of_year,
    extract(month from full_date)::int         as month,
    to_char(full_date, 'Month')                as month_name,
    extract(quarter from full_date)::int       as quarter,
    extract(year from full_date)::int          as year,
    (extract(dow from full_date) in (0, 6))    as is_weekend
from date_spine