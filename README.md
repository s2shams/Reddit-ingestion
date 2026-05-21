# ETL Framework

Hi, I'm Sheehan. This repo is part ETL framework, part portfolio, and part personal project space where I work on ideas that seem fun or interesting to me. A lot of the structure behind it comes from things I learned during past internships, especially my most recent one with the data engineering team at Ford, but the projects themselves are often tied pretty closely to my own interests. You’ll probably notice that a lot of them connect back to hobbies of mine. I play a lot of Genshin, Chess, watch a lot of anime, and read manga, spend a lot of time on reddit, so those topics tend to show up pretty naturally in the kinds of projects I build.

---

Lightweight ETL framework for building, deploying, orchestrating, and monitoring reusable data pipelines on GCP.

The goal of this repository is to keep ETL-specific code small by standardizing the surrounding framework:

- Python ETL execution
- dbt model execution
- Cloud Run job deployment
- Cloud Scheduler orchestration
- BigQuery loading and process tracking
- Shared logging and utility patterns

## What This Framework Does

This repository provides a consistent pattern for defining jobs as a sequence of steps and running them in the same way across environments.

At a high level:

1. A job is defined in `jobs/definitions/<job-name>.txt`
2. Each step is executed by `jobs/runtime/job_runner.py`
3. Python ETLs live in `PythonETLs/`
4. dbt models live in `dbtProject/`
5. Cloud Run jobs and Cloud Scheduler schedules are deployed from `jobs/runtime/deploy_jobs.py`

## Repository Structure

```text
ETL_Framework/
|-- PythonETLs/
|   |-- reddit_ingestion/        # Example ETL implementation
|   `-- utils/                   # Shared ETL utilities
|-- dbtProject/
|   |-- models/                  # dbt models
|   `-- macros/                  # dbt macros
|-- jobs/
|   |-- config/
|   |   |-- jobs_config.json     # Job deployment config
|   |   `-- job_owners.json      # Failure notification owners
|   |-- definitions/             # Job step definitions
|   `-- runtime/                 # Job runner, deploy scripts, entrypoints
|-- dockerfile
|-- requirements.txt
`-- AGENTS.md
```

## Core Patterns

### 1. Shared utilities first

Reusable logic belongs in `PythonETLs/utils/` whenever possible. Current shared utilities include:

- BigQuery client creation
- SQL execution against BigQuery
- Processing status lookup and updates
- NDJSON loading to BigQuery
- Structured JSON logging

### 2. Jobs are step-based

Each job is declared as plain text in `jobs/definitions/`.

A single job can contain one step or multiple steps. That means one job definition file can run multiple Python scripts, multiple dbt selections, or a mix of both, one line at a time in sequence.

Example:

```text
python: PythonETLs/reddit_ingestion/raw_ingest.py
```

or

```text
dbt: dummy_table_for_updates
```

Example with multiple steps in one job:

```text
python: PythonETLs/example_etl/extract.py
python: PythonETLs/example_etl/load.py
dbt: downstream_model
```

The runner supports these step prefixes today:

- `python`
- `dbt`

Ideal practice is for each job to be idempotent for its intended day range or processing window, so reruns are safer and operational recovery is easier. In practice, that is the goal for the framework, but it is not always guaranteed for every pipeline.

### 3. Environment-aware execution

Both Python ETLs and dbt runs use a target environment. The framework currently supports:

- `dev`
- `prod`

Project IDs are mapped in [PythonETLs/utils/etlconfig.py](PythonETLs/utils/etlconfig.py), and dbt targets are configured in [dbtProject/profiles.yml](dbtProject/profiles.yml).

## Local Setup

### Prerequisites

- Python installed and available on `PATH`
- `dbt` installed
- `gcloud` installed
- Access to the relevant GCP projects
- BigQuery authentication available locally

Install dependencies:

```powershell
pip install -r requirements.txt
```

## Running Jobs Locally

Run a job through the same entrypoint Cloud Run uses:

```powershell
$env:TARGET="dev"
python jobs/runtime/cloudrun_entry.py reddit-ingestion
```

You can also run a Python ETL directly:

```powershell
python PythonETLs/reddit_ingestion/raw_ingest.py --target dev
```

Run the dbt adhoc job locally:

```powershell
$env:TARGET="dev"
dbt run --select dummy_table_for_updates --target dev --profiles-dir dbtProject --project-dir dbtProject
```

## Deploying Jobs to GCP

Deployment is handled by [jobs/runtime/deploy_jobs.py](jobs/runtime/deploy_jobs.py).

It reads [jobs/config/jobs_config.json](jobs/config/jobs_config.json) and will:

- update or create the Cloud Run job
- update or create the Cloud Scheduler job when a schedule is configured

Example:

```powershell
$env:SA_EMAIL="your-service-account@your-project.iam.gserviceaccount.com"
python jobs/runtime/deploy_jobs.py --project ingestion-dev-495504 --target dev
```

Current deployment settings include values such as:

- CPU
- memory
- timeout
- retries
- schedule

## How To Add a New ETL

1. Create the ETL code under `PythonETLs/<etl_name>/`
2. Reuse shared utilities from `PythonETLs/utils/` before adding new ETL-specific logic
3. Add a job definition in `jobs/definitions/<job-name>.txt`
4. Add deployment config in `jobs/config/jobs_config.json`
5. Add an owner in `jobs/config/job_owners.json` if failure notification is needed
6. Follow the standard ETL flow:

- read config and environment variables
- initialize the custom logger
- get the last successful run timestamp
- extract data
- load staging/raw data
- run transforms or merges
- update processing status only after success

## Logging

The framework uses a shared JSON logger from [PythonETLs/utils/etllogger.py](PythonETLs/utils/etllogger.py).

This is intended to make Cloud Run logs easier to query and debug. Avoid `print()` in ETL code unless there is a strong reason.

## Notes

- The repository should be run from the project root.
- `jobs/runtime/job_runner.py` is the central execution path for step-based jobs.
- dbt variables are defined in [dbtProject/dbt_project.yml](dbtProject/dbt_project.yml).

## Old_Unmigrated

The [Old_Unmigrated](Old_Unmigrated) folder contains older ETLs and analysis work that have not yet been converted to use the shared utility functions in this framework.

These projects are still useful as references for earlier work and problem areas I have explored, but they are not currently the main focus of the framework. There are plans to migrate them over time, although that work is lower priority than improving and extending the active framework patterns.

If you want to look through them, feel free to do so. They provide context on legacy implementations and the kinds of analyses and ETLs that this framework is gradually standardizing.
