# ------------- Common code --------------
from datetime import datetime, timedelta, timezone
import sys
import os
import argparse
# Set working directory
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from utils.etlmodules import (
    get_last_run_time,
    update_processing_status,
    log_memory_usage,
    load_ndjson_to_BQ,
    truncate_tbl,
    load_data_to_BQ
)
from utils.etllogger import get_logger

# Initialize logger
logger = get_logger(job_name='reddit_ingestion')
parser = argparse.ArgumentParser()
query_dir = os.path.join(os.path.dirname(__file__), 'queries')
# ------------- Common code --------------

# ------------- ETL specific imports --------------
from api_utils import (
    build_posts_request,
    make_api_request,
    process_response_json
)

from config import (
    SUBREDDITS,
    INGEST_FLOW_NAME,
    TEMP_FILE,
    LOG_FREQUENCY,
    TABLE_ID,
    STAGING_TABLE_ID,
    LOAD_CONFIG,
    DEFAULT_DAYS_AGO
)

from gcs_writer import Gcs_writer

# ------------- ETL specific imports --------------

# parse command line arguments
parser.add_argument('--target', '-t', type=str, default='dev', choices=['dev', 'prod'], help='Target environment for the ETL run')
parser.add_argument('--start_time', type=str, default=None, help='Optional start time in either ISO8601 or epoch')
parser.add_argument('--end_time', type=str, default=None, help='Optional end time in either ISO8601 or epoch')
args = parser.parse_args()
start_arg = args.start_time
end_arg = args.end_time

if (start_arg is None) != (end_arg is None):
    logger.error("You must provide BOTH start_time and end_time, or neither.")
    exit(1)

failed_subreddits = []

# Function to ingest data for a single subreddit given a time range
def ingest_subreddit(subreddit, start_time, end_time, loop_counter, writer):
    after = start_time
    before = end_time
    posts, comments = 0, 0

    try:
        while True:
            request = build_posts_request(after, before, subreddit)
            response = make_api_request(request, logger=logger)
            batch_data, after, num_posts, num_comments = process_response_json(response, logger=logger)

            if not batch_data:
                logger.info(f'All posts processed for subreddit: {subreddit}')
                break
            
            loop_counter += 1
            if loop_counter > 0 and loop_counter % LOG_FREQUENCY == 0:
                log_memory_usage(f"After processing {loop_counter} batches")

            writer.write_batch(batch_data)
            posts += num_posts
            comments += num_comments
        return loop_counter, posts, comments
    except Exception as e:
        logger.error(f"Error occurred while ingesting {subreddit}: {e}")
        failed_subreddits.append(subreddit)
        return loop_counter, 0, 0

def ingest_reddit():
    subreddit_status = None
    final_load_status = True
    
    truncate_tbl(STAGING_TABLE_ID)
    lastETLdate = get_last_run_time(INGEST_FLOW_NAME)
    if lastETLdate is None:
        logger.info(f'No previous ETL run found, defaulting to ingesting post data from the start of the day {DEFAULT_DAYS_AGO} days prior to current date')
        lastETLdate = datetime.now(timezone.utc) - timedelta(days=DEFAULT_DAYS_AGO)
        lastETLdate = lastETLdate.replace(hour=0, minute=0, second=0, microsecond=0)

        ETLcutofftime = datetime.now(timezone.utc) - timedelta(days=7)
        ETLcutofftime = ETLcutofftime.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        logger.info(f'Previous ETL run found with last run time: {lastETLdate}.')
        ETLcutofftime = lastETLdate + timedelta(days=1)

    if start_arg and end_arg:
        logger.info(f"Custom time range was provided. ETL time range will be overwritten")
    # convert to correct format for API request
    start_time = lastETLdate.strftime('%Y-%m-%dT%H:%M:%SZ') if start_arg is None else start_arg
    end_time = ETLcutofftime.strftime('%Y-%m-%dT%H:%M:%SZ') if end_arg is None else end_arg
    logger.info(f'Starting to ingest reddit data between time range: {start_time} to {end_time}')
    loop_counter, posts, comments = 0, 0, 0
    writer = Gcs_writer(TEMP_FILE)

    logger.info(f"Subreddits being ingested: {SUBREDDITS}")
    for subreddit in SUBREDDITS:
        loop_counter, num_posts, num_comments = ingest_subreddit(subreddit, start_time, end_time, loop_counter, writer)
        posts += num_posts
        comments += num_comments
    
    writer.close()
    logger.info(f"All subreddits have been ingested. Total posts: {posts} | Total comments: {comments}")
    
    if os.path.exists(TEMP_FILE) and os.path.getsize(TEMP_FILE) > 0:
        logger.info("Uploading final chunk of data to BQ")
        try:
            load_ndjson_to_BQ(TEMP_FILE, STAGING_TABLE_ID, LOAD_CONFIG)
            final_load_status = True
        except Exception as e:
            logger.error(f"Error occurred while loading final ndjson to {TABLE_ID}: {e}")
            final_load_status = False
        finally:
            os.remove(TEMP_FILE)

    if failed_subreddits:
        logger.error(f"The following subreddits failed ingestion: {failed_subreddits}")
        subreddit_status = False
    else:
        subreddit_status = True

    if not (subreddit_status and final_load_status):
        logger.failure(f"An error occurred while ingesting reddit between {start_time} - {end_time}. Will not be proceeding with final merge.")
        exit(1)
    
    try:
        logger.info(f"Starting execution of merge into {TABLE_ID}")
        dataset, table = TABLE_ID.split(".")
        load_data_to_BQ(
            dataset,
            table,
            "reddit_merge",
            query_dir=query_dir,
            merge_query=True
        )
    except Exception as e:
        logger.failure("Merge statement failed. Exiting without updating processing status table")
        exit(1)
    
    # update proc status now
    try:
        update_processing_status(INGEST_FLOW_NAME, ETLcutofftime.strftime('%Y-%m-%d %H:%M:%S'))
        logger.success("reddit-ingestion ran sucessfully")
    except Exception as e:
        exit(1)

def main():
    ingest_reddit()

if __name__ == '__main__':
    main()
