-- models/staging/stg_telegram_messages.sql
-- Cleans and standardizes raw.telegram_messages:
--   * casts types
--   * renames columns to consistent naming
--   * filters out invalid records (empty text, null message_id)
--   * adds calculated fields: message_length, has_image

with source as (

    select * from {{ source('raw', 'telegram_messages') }}

),

cleaned as (

    select
        message_id::bigint                         as message_id,
        channel::text                               as channel_name,
        date::timestamptz                           as message_date,
        trim(text)                                  as message_text,
        coalesce(views, 0)::int                     as view_count,
        coalesce(forwards, 0)::int                   as forward_count,
        media,
        image_path,
        length(trim(text))                          as message_length,
        (image_path is not null)                    as has_image
    from source
    where message_id is not null
      and text is not null
      and trim(text) <> ''

)

select * from cleaned