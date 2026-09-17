"""Child-process exit probe restricted to random local cleanup fixtures."""
from datetime import datetime
import json
import os
from pathlib import Path
import re
import sys

from caseflow_worker import cleanup


def main():
    if not re.fullmatch(r'caseflow_test_[a-f0-9]{32}', os.getenv('DB_NAME', '')):
        raise ValueError('probe requires isolated test database')
    if os.getenv('DB_HOST', '127.0.0.1') != '127.0.0.1' or os.getenv('DB_PORT', '54320') != '54320':
        raise ValueError('probe requires local database')
    if os.getenv('S3_ENDPOINT', 'http://127.0.0.1:8333') != 'http://127.0.0.1:8333' or cleanup.BUCKET != 'caseflow-local':
        raise ValueError('probe requires local fixture storage')
    input_path, output_path, boundary, now = sys.argv[1:]
    report = json.loads(Path(input_path).read_text())
    with cleanup.DeletionJournal(output_path, report) as journal:
        append = journal.append
        def terminate(record):
            if boundary == 'result' and record['event'] == 'DELETE_RESULT':
                os._exit(73)  # Actual delete completed, but no durable result exists.
            append(record)
            if boundary == 'intent' and record['event'] == 'DELETE_INTENT':
                os._exit(73)  # Intent is flushed/fsynced; no delete has been sent.
        journal.append = terminate
        cleanup.apply(report, journal, now=datetime.fromisoformat(now))
    raise AssertionError('boundary was not reached')


if __name__ == '__main__':
    main()
