# AGENTS.md

## Project Overview

This repository is a lightweight ETL framework for building, deploying, orchestrating, and monitoring data pipelines on GCP.

The main goal of this framework is to standardize reusable ETL patterns so that individual ETLs require as little ETL-specific code as possible.

Core priorities:
- Reusable ETL patterns
- Standardized deployment
- Standardized orchestration
- Standardized monitoring and process tracking
- Minimize ETL-specific code
- Maximize shared utility usage
- Maintainable and readable solutions
- Consistent development patterns across ETLs

Core technologies:
- Python
- SQL
- BigQuery
- dbt
- GCP Cloud Run
- GCP Cloud Workflows
- GCP Cloud Scheduler
- GitHub Actions
- Docker

---

## Development

Prioritize maintainability, readability, and consistency over extreme efficiency.

If there is a tradeoff between a simple maintainable solution and a more optimized complex solution:

- Prefer the maintainable solution by default
- Explain the efficiency tradeoff
- Let the analyst decide whether additional optimization is worthwhile

Avoid over-engineering unless there is a clear reason.

Prefer solutions that are easy to debug, extend, and support over solutions that are highly optimized but difficult to understand.

---

## Repository

Assume the project is executed from the repository root.

Avoid solutions requiring manual working directory changes unless necessary.

Prefer imports and project structure that function correctly when commands are executed from the project root.

---

## Utility Function Usage

ETL-specific code should be minimized as much as possible.

Before writing new ETL-specific logic:

1. Check whether a shared utility function already exists
2. Reuse existing utility functions where possible
3. Extend shared utility functions if logic is reusable across ETLs
4. Only write ETL-specific logic when functionality is genuinely unique

Do not duplicate common logic such as:

- Logging setup
- BigQuery client creation
- BigQuery loading
- SQL execution
- Process status tracking
- Config loading
- API request handling
- Retry logic
- Temporary file handling
- Deployment logic
- Orchestration logic

Framework logic should live in reusable utilities whenever possible.

---

## Logging Rules

Do not use `print()` statements unless specifically asked.

Always prioritize the custom logger defined in the utility folder.

Every ETL should log:

- ETL name
- Start time
- End time
- Source time range
- Number of records extracted
- Number of records loaded
- Destination dataset/table
- Success/failure status
- Useful exception details

Logs should be useful within Cloud Run without requiring local reproduction.

---

## Code Style

Use:

- `snake_case` for variables, functions, files, and table names
- Clear function names
- Small reusable functions
- Explicit parameters instead of hidden globals
- Type hints where helpful
- Shared utility functions before ETL-specific implementations
- Custom logger instead of `print()`

When asked to create or update a function docstring, the docstring should explain:

- Purpose of the function
- Expected inputs
- Expected outputs
- Important side effects if applicable

Do not generate large or overly formal docstrings unless specifically requested.

Comments should be used where helpful, but not excessively.

Good comments explain:

- Why logic exists
- Non-obvious implementation decisions
- Edge case handling

Avoid comments that only repeat what the code already says.

Bad:

```python
i += 1 # increase i by one
```

Good:

```python
# Add overlap window to avoid missing delayed API records
```

---

## Branch Naming

All branches must follow:

```text
topic/ss/[feature-or-update-being-implemented]
```

Do not skip the `topic/ss/` prefix.

---

## ETL Design Pattern

Most ETLs should follow this flow:

1. Read config/environment variables
2. Initialize custom logger
3. Get last successful run timestamp or watermark
4. Extract source data
5. Write temporary raw data if necessary
6. Load staging/raw data through shared utilities
7. Run SQL or dbt transformations
8. Update process status after successful completion
9. Log success or failure

Do not update process status before downstream processes complete successfully.

---

## BigQuery Guidelines

Prefer:

- Partitioning large tables
- Clustering frequently filtered fields

Avoid:

- Blind `WRITE_TRUNCATE`
- Dropping production tables
- Loading directly into final reporting tables
- Assuming BigQuery enforces primary keys

Logical primary keys should be documented.

---

## Change Management Behavior

Unless explicitly instructed otherwise, do not immediately modify files.

Default workflow:

1. Inspect current implementation
2. Explain proposed changes in chat
3. Show exact code or suggested diff
4. Allow the analyst to modify or approve changes

Only directly implement changes when explicitly requested:

Examples:

- "Apply this"
- "Update the code"
- "Modify the file"
- "Implement this"

Assume analyst review happens before implementation.

---

## Preferred AI Behavior

When asked to make changes:

1. Inspect existing framework patterns first
2. Reuse utility functions wherever possible
3. Preserve existing interfaces unless redesign is requested
4. Propose changes before modifying files
5. Show exact code or diffs when useful
6. Explain assumptions
7. Explain tradeoffs
8. Identify risks and edge cases
9. Avoid rewriting unrelated code
10. Prioritize maintainability and readability
11. Avoid introducing ETL-specific logic if framework logic is more appropriate

When generating new ETLs:

- Follow existing framework patterns
- Extend reusable utilities before adding duplicated code
- Avoid inventing entirely new patterns without reason

---

## Safety Rules

Never:

- Commit secrets
- Hardcode service account keys
- Hardcode environment-specific values unnecessarily
- Drop production tables without explicit confirmation
- Update process state after failed ETLs
- Hide exceptions without logging them

When uncertain, choose the safer implementation and explain tradeoffs.

## Adhoc Change Guidelines

For one-time adhoc changes that can be implemented through dbt:

Use the `dummy_table_for_updates` model and place the adhoc SQL logic inside the model's `post_hook`.

Purpose:
- Keep one-time updates standardized
- Avoid creating unnecessary permanent models
- Maintain visibility of historical adhoc changes
- Avoid embedding temporary update logic into production ETLs

Example pattern:

```sql
{{ config(
    materialized='table',
    post_hook=[
        """
        UPDATE target_table
        SET status = 'processed'
        WHERE created_date < '2026-01-01'
        """
    ]
) }}

SELECT 1 AS dummy_column
```

Guidelines:

- Keep adhoc logic isolated to the `post_hook`
- Include comments explaining the purpose of the change
- If possible, ensure the query is idempotent. Always comment whether it is or isn't
- Avoid placing adhoc business logic directly into production dbt models
- Avoid modifying ETL logic for temporary one-time fixes