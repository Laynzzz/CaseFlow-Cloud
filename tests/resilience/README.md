# Local dependency restart evidence

These opt-in tests stop and start **disposable** PostgreSQL and Kafka containers,
using the production Python worker retry loops. Ports `127.0.0.1:55432` and
`127.0.0.1:19092` must be free. Existing `caseflow-local` containers, databases,
topics and consumer groups are never selected. No model calls or cloud services
are involved.

From the repository root in PowerShell:

```powershell
. ./scripts/dev-env.ps1
$env:CASEFLOW_RESTART_TESTS='1'
$env:CASEFLOW_RESTART_RUN_ID='restart-' + (Get-Date -Format yyyyMMdd-HHmmss)
services/worker/.venv/Scripts/python.exe -m pytest tests/resilience -q --junitxml="output/r3-dependency-restart/$env:CASEFLOW_RESTART_RUN_ID/junit.xml"
```

The local environment script loads ignored credentials into process environment;
the commands do not print credentials. Each run creates a UUID-named Compose
project, with the same pinned PostgreSQL/Kafka image digests as the local stack.
The server container IDs and named-volume mounts are checked before and after
restart. Cleanup verifies names and Docker Compose project labels before removing
each owned container, volume or network. It never uses a global prune.

- Kafka: start the actual publisher with a pending production outbox record,
  observe a `KafkaException` while the broker is stopped, confirm the event stays
  unpublished, restart the same persisted broker, and observe the same runtime
  publish the same event ID. Assert one broker record, one outbox record and no
  duplicate job/inbox business records.
- PostgreSQL: pause after production scheduling SQL and before commit, stop the
  server, release the transaction, and observe the real commit exception. The
  Kafka offset must remain uncommitted. Restart the same persisted server, inspect
  that neither job nor inbox committed, then let the same consumer retry. Replay
  the request again to prove one durable job/inbox and advancing offsets.

Only a transaction checkpoint, log observation and test topic/group settings are
instrumented; failed database commits and broker deliveries come from actual
unavailable services. The PostgreSQL checkpoint delays recovery briefly so the
rolled-back state can be measured before the worker proceeds.

`manifest.json` records revision, source SHA-256 hashes, command, versions,
endpoints, timestamps and limitations. `events.json` retains safe Docker command
output, IDs, observed retry errors and durable before/after state. JUnit records
the assertions and recovery results. Raw artifacts are generated under
`output/r3-dependency-restart/<run-id>/`; use a new run ID each time.

For sensitivity evidence, set `$env:CASEFLOW_RESTART_NEGATIVE_CONTROL='kafka'`
and run only `-k kafka_restart`. This intentionally omits the broker stop; the
test **must fail** because it observes no unavailable-broker publish failure.
Unset the variable before a normal run. The equivalent `postgres` control omits
the database stop and must fail because scheduling commits successfully. These
controls are expected failures, not release results.

Without `CASEFLOW_RESTART_TESTS=1`, restart tests skip; resource-guard tests still
run. This proves local dependency restart recovery for selected production worker
loops. It does not prove a full application deployment, Java completion handling,
cloud failover, host restart, multi-node Kafka durability, or arbitrary outages.
