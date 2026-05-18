{{ config(
    materialized='table',
    post_hook=[
        "{{ update_proc_status('reddit_ingestion_test', '2026-05-17 12:00:00', true) }}"
    ]
) }}

SELECT DATETIME('{{ get_last_run_date('reddit_ingestion') }}') as test_value