-- tests/assert_no_future_messages.sql
-- Business rule: no message should be dated after today.
-- This test passes when it returns 0 rows.

select
    fm.message_id,
    dd.full_date
from {{ ref('fct_messages') }} fm
join {{ ref('dim_dates') }} dd
    on fm.date_key = dd.date_key
where dd.full_date > current_date