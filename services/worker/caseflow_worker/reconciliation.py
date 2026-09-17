"""Bounded operational findings. This report never repairs or republishes work."""
from .settings import database


def reconcile(*, age_seconds: int = 300, limit: int = 100) -> dict:
    if type(age_seconds) is not int or not 60 <= age_seconds <= 2_592_000:
        raise ValueError('age_seconds must be between 60 and 2592000')
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError('limit must be between 1 and 1000')
    with database() as db:
        db.execute('SET TRANSACTION READ ONLY')
        observed_at = db.execute('SELECT now() AS at').fetchone()['at']
        rows = db.execute("""
            WITH signals AS (
                SELECT * FROM core.worker_operation_signals
                WHERE observed_at < now() - %s * interval '1 second'
                UNION ALL
                SELECT 'EXPIRED_LEASE', tenant_id, case_id, job_id, NULL::uuid, lease_until
                FROM worker.jobs WHERE status='RUNNING' AND lease_until < now()
                UNION ALL
                SELECT 'OVERDUE_JOB', tenant_id, case_id, job_id, NULL::uuid, available_at
                FROM worker.jobs WHERE status IN ('QUEUED','RETRY_WAIT')
                  AND available_at < now() - %s * interval '1 second'
                UNION ALL
                SELECT 'WORKER_OUTBOX_PENDING', tenant_id, NULL::uuid, job_id, event_id, created_at
                FROM worker.outbox WHERE published_at IS NULL
                  AND created_at < now() - %s * interval '1 second'
            ) SELECT * FROM signals
            ORDER BY observed_at, kind, tenant_id, job_id, event_id, case_id
            LIMIT %s
            """, (age_seconds, age_seconds, age_seconds, limit + 1)).fetchall()
    findings = [{
        'kind': row['kind'],
        **{public: str(row[column]) if row[column] is not None else None
           for public, column in [('tenantId', 'tenant_id'), ('caseId', 'case_id'),
                                  ('jobId', 'job_id'), ('eventId', 'event_id')]},
        'ageSeconds': max(0, int((observed_at - row['observed_at']).total_seconds())),
    } for row in rows[:limit]]
    return {'schemaVersion': 1, 'status': 'ATTENTION' if findings else 'NO_FINDINGS',
            'observedAt': observed_at.isoformat(), 'thresholdSeconds': age_seconds,
            'limit': limit, 'truncated': len(rows) > limit, 'findings': findings}
