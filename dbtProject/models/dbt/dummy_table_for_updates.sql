{{ config(
    materialized='table',
    post_hook=[
        "{{ update_proc_status('reddit_ingestion_test', '2026-05-17 12:00:00', true) }}"
    ]
) }}

select 1 as test_value