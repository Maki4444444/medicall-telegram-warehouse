-- models/marts/fct_messages.sql
-- Fact table: one row per message, with FKs to dim_channels and dim_dates.

with stg as (

    select * from {{ ref('stg_telegram_messages') }}

),

channels as (

    select channel_key, channel_name from {{ ref('dim_channels') }}

),

dates as (

    select date_key, full_date from {{ ref('dim_dates') }}

)

select
    stg.message_id,
    channels.channel_key,
    dates.date_key,
    stg.message_text,
    stg.message_length,
    stg.view_count,
    stg.forward_count,
    stg.has_image
from stg
left join channels
    on stg.channel_name = channels.channel_name
left join dates
    on stg.message_date::date = dates.full_date