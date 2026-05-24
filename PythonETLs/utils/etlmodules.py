from .etllogger import get_logger
import os
import datetime
from google.cloud import bigquery
import psutil

from .etlconfig import (
    get_project_id,
    get_BQ_client,
    MEM_WARNING_THRESHOLD
)
logger = get_logger(__name__)
_client = None
project_id = get_project_id(os.getenv('target', 'dev'))
query_dir = os.path.join(os.path.dirname(__file__), 'sql_scripts')

def get_client():
    """Return a cached BigQuery client for the current target environment.

    Uses the `target` environment variable to determine whether to connect to dev,
    prod, or another configured target. The client instance is cached in the
    module-level `_client` variable so repeated calls reuse the same object.
    """
    global _client
    if _client is None:
        target = os.getenv('target', 'dev')
        _client = get_BQ_client(target)
    return _client

def load_data_to_BQ(destDatasetName, destTableName, queryName, query_dir=query_dir, project_id=project_id, write_disposition='WRITE_APPEND', job_config=None, merge_query=False):
    """Execute a parameterized SQL query and load its results into BigQuery.

    Reads a SQL file from `query_dir`, substitutes placeholder values for the
    destination dataset, table, and project, then runs the query in BigQuery.
    The query job is awaited until completion and the result is returned.

    Args:
        destDatasetName: Target BigQuery dataset name.
        destTableName: Target BigQuery table name.
        queryName: Filename of the SQL query to execute.
        query_dir: Directory containing SQL query files.
        project_id: BigQuery project ID used when rendering the query.
        write_disposition: BigQuery write disposition mode.
        job_config: Optional BigQuery job configuration.
    """
    client = get_client()
    query_path = os.path.join(query_dir, f'{queryName}.sql')
    
    with open(query_path, 'r') as f:
        query = f.read()
        query = query.replace('DEST_DATASET_NAME', destDatasetName)
        query = query.replace('DEST_TABLE_NAME', destTableName)
        query = query.replace('DEST_PROJECT_ID', project_id)
    
    if job_config is None:
        job_config = bigquery.QueryJobConfig()
        if not merge_query:
            job_config.write_disposition = write_disposition
    
    try:
        query_job = client.query(query, job_config=job_config)
        query_job.result() # Wait for the job to complete

        num_rows = query_job.num_dml_affected_rows if query_job.num_dml_affected_rows is not None else 'N/A'
        time_taken = (query_job.ended - query_job.started).total_seconds()
        logger.success(f'Successfully loaded data to {destDatasetName}.{destTableName}. Rows affected: {num_rows}, Time taken: {time_taken:.2f}')

        return query_job
    except Exception as e:
        logger.error(f'Error occurred while loading data to {destDatasetName}.{destTableName}: {e}')
        raise

# Checks if a data flow exists in the processing_status table
def check_flow_exists(data_flow_name):
    """Return whether a processing status flow exists for the given name.

    Executes the SQL query that checks `processing_status` for the supplied
    `data_flow_name` and returns the boolean result.
    """
    client = get_client()
    query_path = os.path.join(query_dir, 'check_flow_exists.sql')

    with open(query_path, 'r') as f:
        query = f.read()
        query = query.replace('DATA_FLOW_NAME', data_flow_name)

    try:
        query_job = client.query(query)
        result = query_job.result()
        flow_exists = None
        for row in result:
            flow_exists = row.flow_exists
        logger.info(f'Flow existence check for "{data_flow_name}": {flow_exists}')
        return flow_exists
    except Exception as e:
        logger.error(f'Error occurred while checking flow existence for "{data_flow_name}": {e}')
        raise

# Returns the last etl_datetime from processing_status or none of data_flow_name doesn't exist in the table
def get_last_run_time(data_flow_name):
    """Fetch the last ETL runtime for the named data flow.

    If the flow does not exist in `processing_status`, returns None. Otherwise,
    queries the last recorded `etl_datetime` for that flow and returns it.
    """
    client = get_client()
    query_path = os.path.join(query_dir, 'last_run_time.sql')

    if not check_flow_exists(data_flow_name):
        logger.info(f'No existing flow found for "{data_flow_name}". Returning None for last run time.')
        return None
    
    with open(query_path, 'r') as f:
        query = f.read()
        query = query.replace('DATA_FLOW_NAME', data_flow_name)
    
    try:
        query_job = client.query(query)
        result = query_job.result()
        last_run_time = None
        for row in result:
            last_run_time = row.etl_datetime
        logger.info(f'Last run time for "{data_flow_name}": {last_run_time}')
        return last_run_time
    except Exception as e:
        logger.error(f'Error occurred while retrieving last run time for "{data_flow_name}": {e}')
        raise

def update_processing_status(data_flow_name, etl_datetime):
    """Insert or update the processing status row for a data flow.

    Determines whether the flow already exists and then executes the
    appropriate insert or update SQL statement. Logs the action and returns
    once the status update has been applied.
    """
    client = get_client()
    query_path = None

    if check_flow_exists(data_flow_name):
        query_path = os.path.join(query_dir, 'update_proc_status.sql')
        logger.info(f'Updating existing processing status for "{data_flow_name}" with new etl_datetime: {etl_datetime}')
    else:
        query_path = os.path.join(query_dir, 'insert_proc_status.sql')
        logger.info(f'Inserting new processing status for "{data_flow_name}" with etl_datetime: {etl_datetime}')
    
    with open(query_path, 'r') as f:
        query = f.read()
        query = query.replace('DATA_FLOW_NAME', data_flow_name)
        query = query.replace('ETL_DATETIME', etl_datetime)
    
    try:
        query_job = client.query(query)
        query_job.result() # Wait for the job to complete
        logger.success(f'Successfully updated processing status for "{data_flow_name}" with etl_datetime: {etl_datetime}')
    except Exception as e:
        logger.error(f'Error occurred while updating processing status for "{data_flow_name}": {e}')
        raise

def log_memory_usage(msg, silent=False):
    mem = psutil.virtual_memory()
    total = mem.total / (1024 ** 2)
    available = mem.available / (1024 ** 2)
    used = mem.used / (1024 ** 2)

    if not silent:
        logger.info(f"Memory usage: {msg}")
        logger.info(
            f"Total Memory: {total:.2f} MB | "
            f"Used Memory: {used:.2f} MB ({mem.percent:.2f}%) | "
            f"Available: {available:.2f} MB"
        )
    
    if mem.percent >= MEM_WARNING_THRESHOLD:
        return 'warning'
    else:
        return 'normal'
    
def load_ndjson_to_BQ(path, table_id, job_config):
    client = get_client()

    try:
        with open(path, "rb") as f:
            job = client.load_table_from_file(f, table_id, job_config=job_config)
        job.result()
        logger.info("Sucessfully loaded file to BQ")
    except Exception as e:
        logger.error(f"Failed to upload file to BQ: {e}")
        raise

def if_tbl_exists(table_id):
    client = get_client()

    try:
        client.get_table(table_id)
        return True
    except Exception:
        return False

def truncate_tbl(table_id):
    client = get_client()

    if not if_tbl_exists(table_id):
        logger.warning(f"Cannot truncate {table_id}, as it does not exists")
        return
    
    query = f"""
    TRUNCATE TABLE {table_id}
    """
    job = client.query(query)
    job.result()

