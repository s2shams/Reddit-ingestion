import sys
import shlex
import subprocess
import os
from jobs.runtime.etl_utils import send_email, get_owner_email
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

def run_python(script_path, args):
    cmd = [
        "python",
        script_path,
        "--target",
        get_target()
    ] + args

    print("Running:", " ".join(cmd), flush=True)
    return subprocess.run(cmd).returncode

def run_dbt(args):
    cmd = [
        "dbt"
    ] + args + [
        "--target",
        get_target(),
        "--profiles-dir",
        DBT_PROJECT_FOLDER,
        "--project-dir",
        DBT_PROJECT_FOLDER
    ]

    print("Running:", " ".join(cmd), flush=True)
    return subprocess.run(cmd).returncode

def run_job(job_name, file_path):
    email = get_owner_email(job_name)

    with open(file_path) as f:
        steps = [line.strip() for line in f if line.strip()]

    print(f"Starting job: {job_name} | TARGET={get_target()}", flush=True)

    for step in steps:
        prefix, args = parse_line(step)

        if prefix == "python":
            command = args[0]
            exit_code = run_python(command, args[1:0])

        elif prefix == "dbt":
            exit_code = run_dbt(args)

        else:
            raise ValueError(f"Unknown step type: {prefix}")

        if exit_code != 0:
            print(f"\nFAILED STEP: {step}", flush=True)

            if email:
                send_email(job_name, step, email)

            sys.exit(exit_code)

    print(f"Job {job_name} completed successfully", flush=True)