-- tests/assert_positive_views.sql
-- Business rule: view counts must never be negative.
-- This test passes when it returns 0 rows.

select
    message_id,
    view_count
from {{ ref('fct_messages') }}
where view_count < 0