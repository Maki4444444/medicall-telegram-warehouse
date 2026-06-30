-- models/marts/fct_image_detections.sql
-- Joins YOLO detection results (loaded via dbt seed) with fct_messages
-- to bring channel_key and date_key into the detections fact table.

with yolo as (

    select
        message_id::bigint      as message_id,
        channel_name,
        detected_class,
        confidence_score::float as confidence_score,
        image_category
    from {{ ref('yolo_results') }}

),

messages as (

    select message_id, channel_key, date_key
    from {{ ref('fct_messages') }}

)

select
    yolo.message_id,
    messages.channel_key,
    messages.date_key,
    yolo.detected_class,
    yolo.confidence_score,
    yolo.image_category
from yolo
inner join messages
    on yolo.message_id = messages.message_id