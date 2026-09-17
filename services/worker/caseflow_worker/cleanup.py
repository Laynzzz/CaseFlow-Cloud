"""Conservative, explicit document orphan cleanup. Never scheduled automatically.

Only canonical objects of a succeeded job are considered. Apply locks its job
row, then takes an artifact table SHARE lock through a narrow SQL function.
This blocks artifact writes during one external delete, while unrelated job
heartbeats remain available. It deliberately trades brief artifact selection
blocking for a stable cross-job reference check.
"""
from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import re
from uuid import UUID, uuid4

import boto3
from botocore.config import Config

from .settings import BUCKET, database

_UUID = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
_KEY = re.compile(rf'tenants/({_UUID})/documents/({_UUID})/attempt-([1-9][0-9]*)/fence-([1-9][0-9]*)/({_UUID})\.docx')


def storage():
    """Short single-attempt storage calls bound time spent holding SQL locks."""
    options = dict(region_name=os.getenv('AWS_REGION', 'us-east-1'),
                   config=Config(connect_timeout=2, read_timeout=3,
                                 retries={'total_max_attempts': 1}, s3={'addressing_style': 'path'}))
    endpoint = os.getenv('S3_ENDPOINT', 'http://127.0.0.1:8333')
    if endpoint:
        options.update(endpoint_url=endpoint, aws_access_key_id=os.environ['S3_ACCESS_KEY'],
                       aws_secret_access_key=os.environ['S3_SECRET_KEY'])
    return boto3.client('s3', **options)


def canonical_id(value):
    if not isinstance(value, str) or str(UUID(value)) != value:
        raise ValueError('CANONICAL_UUID_REQUIRED')
    return value


def classify_key(key, tenant, job):
    match = _KEY.fullmatch(key) if isinstance(key, str) else None
    if not match or match[1] != tenant or match[2] != job:
        return None
    return int(match[3]), int(match[4])


def _validate(tenant, job, grace_hours, limit):
    canonical_id(tenant)
    canonical_id(job)
    if not math.isfinite(grace_hours) or not 24 <= grace_hours <= 87600:
        raise ValueError('GRACE_MUST_BE_24_TO_87600_HOURS')
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError('LIMIT_MUST_BE_1_TO_1000')


def _now(now):
    value = now if now is not None else datetime.now(timezone.utc)
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('TIMEZONE_REQUIRED')
    return value


def _state(db, tenant, job):
    row = db.execute('''SELECT j.kind,j.status,j.attempt,j.fence,a.object_key,
        a.attempt AS artifact_attempt,a.fence AS artifact_fence
        FROM worker.jobs j LEFT JOIN worker.artifacts a USING (tenant_id,job_id)
        WHERE j.tenant_id=%s AND j.job_id=%s''', (tenant, job)).fetchone()
    if not row or row['kind'] != 'DOCUMENT' or row['status'] != 'SUCCEEDED':
        return None
    if (row['attempt'], row['fence']) != (row['artifact_attempt'], row['artifact_fence']):
        return None
    if classify_key(row['object_key'], tenant, job) != (row['attempt'], row['fence']):
        return None
    return dict(row)


def _referenced(db, key):
    return db.execute('SELECT 1 FROM worker.artifacts WHERE object_key=%s', (key,)).fetchone() is not None


def preview(tenant, job, *, grace_hours=24, limit=100, client=None, now=None):
    """Read at most limit objects under one exact prefix; never mutate state."""
    _validate(tenant, job, grace_hours, limit)
    checked_at = _now(now)
    prefix = f'tenants/{tenant}/documents/{job}/'
    report = dict(schemaVersion=1, mode='PREVIEW', tenant=tenant, job=job, bucket=BUCKET,
                  prefix=prefix, graceHours=grace_hours, limit=limit,
                  checkedAt=checked_at.isoformat(), eligible=False, state=None,
                  objects=[], truncated=False)
    with database() as db:
        state = _state(db, tenant, job)
        report.update(eligible=state is not None, state=state)
        if state is None:
            report['reason'] = 'INELIGIBLE_JOB'
            return report
        client = client or storage()
        token = None
        while len(report['objects']) < limit:
            options = dict(Bucket=BUCKET, Prefix=prefix, MaxKeys=limit-len(report['objects']))
            if token:
                options['ContinuationToken'] = token
            page = client.list_objects_v2(**options)
            for item in page.get('Contents', []):
                key = item['Key']
                if classify_key(key, tenant, job) is None:
                    reason = 'MALFORMED'
                elif key == state['object_key']:
                    reason = 'SELECTED'
                elif _referenced(db, key):
                    reason = 'REFERENCED'
                elif item['LastModified'] > checked_at - timedelta(hours=grace_hours):
                    reason = 'FRESH'
                else:
                    reason = 'CANDIDATE'
                report['objects'].append(dict(key=key, reason=reason, etag=item['ETag'],
                    size=item['Size'], lastModified=item['LastModified'].isoformat()))
            report['truncated'] = bool(page.get('IsTruncated'))
            if not report['truncated']:
                break
            next_token = page.get('NextContinuationToken')
            if not next_token or token == next_token:
                raise ValueError('INVALID_STORAGE_PAGINATION')
            token = next_token
    return report


class DeletionJournal:
    """Exclusive append-only JSONL; incomplete final lines imply unknown outcome.

    A durable DELETE_INTENT without a matching durable DELETE_RESULT is pending,
    even if S3 already deleted the object. Never overwrite or resume a journal.
    """
    def __init__(self, path, report):
        self.path = Path(path)
        self.report = report
        self.run_id = str(uuid4())
        self.output = self.path.open('x', encoding='utf-8', newline='\n')
        try:
            self.append(dict(event='START', runId=self.run_id, preview=report))
        except BaseException:
            self.output.close()
            raise

    def append(self, record):
        self.output.write(json.dumps(dict(record, recordedAt=datetime.now(timezone.utc).isoformat()),
                                     sort_keys=True) + '\n')
        self.output.flush()
        os.fsync(self.output.fileno())

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.output.close()


def apply(report, journal, *, client=None, now=None):
    """Apply only this preview's candidates, rechecking state and age per object.

    A timeout may follow an effective delete; report UNKNOWN and stop. Exceptions
    writing journal records propagate, leaving any previous durable intent pending.
    No successful final record is written on an interrupted execution.
    """
    tenant, job = report['tenant'], report['job']
    _validate(tenant, job, report['graceHours'], report['limit'])
    if not isinstance(journal, DeletionJournal) or journal.report is not report or journal.output.closed:
        raise ValueError('MATCHING_OPEN_JOURNAL_REQUIRED')
    if report['bucket'] != BUCKET or report['prefix'] != f'tenants/{tenant}/documents/{job}/':
        raise ValueError('SCOPE_MISMATCH')
    candidates = [item for item in report['objects'] if item['reason'] == 'CANDIDATE']
    if len(report['objects']) > report['limit']:
        raise ValueError('REPORT_EXCEEDS_LIMIT')
    result = dict(deleted=0, skipped=0, unknown=0, notAttempted=len(candidates), truncated=report['truncated'])
    client = client or storage()
    for item in candidates:
        key = item['key']
        operation = str(uuid4())
        with database() as db:
            # Match finalization order: job row first, artifact table second.
            # Existing 3s lock_timeout bounds acquisition. The function only
            # locks artifacts; worker gains no artifact UPDATE/DELETE privilege.
            db.execute('SELECT job_id FROM worker.jobs WHERE tenant_id=%s AND job_id=%s FOR UPDATE',
                       (tenant, job))
            db.execute('SELECT worker.lock_artifacts_for_cleanup()')
            state = _state(db, tenant, job)
            reason = None
            if state is None or state != report['state']:
                reason = 'STATE_CHANGED'
            elif classify_key(key, tenant, job) is None:
                reason = 'MALFORMED'
            elif _referenced(db, key):
                reason = 'REFERENCED'
            if reason is None:
                head = client.head_object(Bucket=BUCKET, Key=key)
                if (head['ETag'] != item['etag'] or head['ContentLength'] != item['size']
                        or head['LastModified'].isoformat() != item['lastModified']):
                    reason = 'OBJECT_CHANGED'
                elif head['LastModified'] > _now(now) - timedelta(hours=report['graceHours']):
                    reason = 'FRESH'
            if reason:
                journal.append(dict(event='SKIP', key=key, reason=reason))
                result['skipped'] += 1
                result['notAttempted'] -= 1
                continue
            journal.append(dict(event='DELETE_INTENT', operationId=operation, key=key,
                                etag=head['ETag'], state=state, outcome='PENDING'))
            try:
                response = client.delete_object(Bucket=BUCKET, Key=key, IfMatch=head['ETag'])
                if response.get('ResponseMetadata', {}).get('HTTPStatusCode') not in (200, 204):
                    raise RuntimeError('UNEXPECTED_DELETE_RESPONSE')
            except Exception as error:
                journal.append(dict(event='DELETE_RESULT', operationId=operation, key=key,
                                    outcome='UNKNOWN', errorType=type(error).__name__))
                result['unknown'] += 1
                result['notAttempted'] -= 1
                break
            journal.append(dict(event='DELETE_RESULT', operationId=operation, key=key,
                                outcome='DELETE_ACKNOWLEDGED'))
            result['deleted'] += 1
            result['notAttempted'] -= 1
    journal.append(dict(event='FINISHED', status='INCOMPLETE' if result['unknown'] else 'COMPLETED', **result))
    return result
