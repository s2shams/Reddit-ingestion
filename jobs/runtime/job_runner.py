import sys
import shlex
import subprocess
import os
import json
from jobs.runtime.etl_utils import send_email, get_owner_email
from PythonETLs.utils.etllogger import get_logger

logger = get_logger("job_runner")
DBT_PROJECT_FOLDER = "dbtProject"

def get_target():
    return os.getenv("TARGET", "dev")

def parse_line(line):
    if ":" not in line:
        raise ValueError(f"Invalid step format: {line}")

    prefix, rest = line.split(":", 1)
    prefix = prefix.strip().lower()

    parts = shlex.split(rest.strip())

    return prefix, parts

def log_dbt_line(logger, line):
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        logger.info(line)
        return
    
    info = event.get("info", {})
    data = event.get("data", {})
    level = info.get("level", "info").lower()
    message = data.get("msg") or info.get("msg") or None

    # Sometimes dbt logs an empty message but the line isn't empty. For our use case, not needed so we just discard
    if message is None:
        return

    if level in {"warn", "warning"}:
        logger.warning(message)
    elif level == "error":
        logger.error(message)
    else:
        logger.info(message)

def run_python(script_path, args):
    cmd = [
        sys.executable, # Mainly to force local runs to use Python installed in .venv. Does not affect docker runs
        script_path,
        "--target",
        get_target()
    ] + args

    # For logging purposes, to avoid logging sys.executable path for cleaner logging
    display_cmd = [
        "python",
        script_path,
        "--target",
        get_target()
    ] + args

    logger.info(f"Running: {' '.join(display_cmd)}")
    return subprocess.run(cmd).returncode

def run_dbt(args):
    cmd = [
        "dbt",
        "run",
        "--select"
    ] + args + [
        "--target",
        get_target(),
        "--profiles-dir",
        DBT_PROJECT_FOLDER,
        "--project-dir",
        DBT_PROJECT_FOLDER,
        "--log-format",
        "json"
    ]

    # run the process, capture output, parse and log it with the framework defined logger
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    if process.stdout is None:
        logger.failure("Failed to capture dbt output. dbt model status is unknown")
        return 1
    
    for line in process.stdout:
        line = line.strip()

        if not line:
            continue

        log_dbt_line(logger=logger, line=line)
    
    return_code = process.wait()

    if return_code == 0:
        logger.success("dbt command completed successfully")
    else:
        logger.failure(f"dbt command failed with return code {return_code}")
    
    return return_code

def run_job(job_name, file_path):
    email = get_owner_email(job_name)

    with open(file_path) as f:
        steps = [line.strip() for line in f if line.strip()]

    logger.info(f"Starting job: {job_name} | TARGET={get_target()}")

    for step in steps:
        prefix, args = parse_line(step)

        if prefix == "python":
            command = args[0]
            exit_code = run_python(command, args[1:])

        elif prefix == "dbt":
            exit_code = run_dbt(args)

        else:
            raise ValueError(f"Unknown step type: {prefix}")

        if exit_code != 0:
            logger.error(f"\nFAILED STEP: {step}")

            if email:
                send_email(job_name, step, email)

            sys.exit(exit_code)

    logger.success(f"Job {job_name} completed successfully")