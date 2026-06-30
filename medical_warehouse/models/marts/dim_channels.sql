-- models/marts/dim_channels.sql
-- Channel dimension: one row per channel with derived attributes.

with stg as (

    select * from {{ ref('stg_telegram_messages') }}

),

channel_type_mapped as (

    select
        channel_name,
        case
            when lower(channel_name) like '%chemed%'   then 'Pharmaceutical'
            when lower(channel_name) like '%lobelia%'  then 'Cosmetics'
            when lower(channel_name) like '%tikvah%'   then 'Pharmaceutical'
            else 'Medical'
        end as channel_type,
        message_date,
        view_count
    from stg

),

aggregated as (

    select
        channel_name,
        max(channel_type)                  as channel_type,
        min(message_date)                  as first_post_date,
        max(message_date)                  as last_post_date,
        count(*)                           as total_posts,
        round(avg(view_count), 2)          as avg_views
    from channel_type_mapped
    group by channel_name

)

select
    row_number() over (order by channel_name) as channel_key,
    channel_name,
    channel_type,
    first_post_date,
    last_post_date,
    total_posts,
    avg_views
from aggregated