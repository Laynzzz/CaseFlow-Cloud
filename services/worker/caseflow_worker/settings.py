import os
import psycopg
from psycopg.rows import dict_row
import boto3
from botocore.config import Config


def database():
    return psycopg.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"), port=int(os.getenv("DB_PORT", "54320")),
        dbname=os.getenv("DB_NAME", "caseflow"), user="caseflow_worker",
        password=os.environ["DB_WORKER_PASSWORD"], connect_timeout=5, row_factory=dict_row,
        options="-c statement_timeout=10000 -c lock_timeout=3000",
    )


def storage():
    endpoint = os.getenv("S3_ENDPOINT", "http://127.0.0.1:8333")
    options = dict(region_name=os.getenv("AWS_REGION", "us-east-1"),
                   config=Config(connect_timeout=3, read_timeout=15, retries={"max_attempts": 2},
                                 s3={"addressing_style": "path"}))
    if endpoint:
        options.update(endpoint_url=endpoint, aws_access_key_id=os.environ["S3_ACCESS_KEY"],
                       aws_secret_access_key=os.environ["S3_SECRET_KEY"])
    return boto3.client("s3", **options)


BUCKET = os.getenv("S3_BUCKET", "caseflow-local")
BROKER = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "127.0.0.1:9092")
REQUEST_TOPIC = "caseflow.jobs.v1"
COMPLETION_TOPIC = "caseflow.completions.v1"
DEAD_TOPIC = "caseflow.deadletters.v1"
