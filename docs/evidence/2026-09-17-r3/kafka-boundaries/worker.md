# Worker process crashes at real Kafka boundaries

Observed September 17, 2026 UTC on the same Windows/local Docker environment
as the [preceding process experiments](../summary.md). Baseline `5f58535`;
worker source committed as `cfaa52b627d443bc73279c93d56de0d0b7264d83`.
The production Python code is unchanged.

## Results

Four actual process-kill scenarios and three isolation guards passed in 18.44
seconds on the final focused run. The full worker suite passed **102 tests in
46.54 seconds**, no failures/errors/skips. JUnit suite properties contain
child PIDs, boundary and termination timestamps, exit codes, event IDs and
broker coordinates. See `r3-worker-kafka-final.xml` and
`r3-worker-kafka-full.xml` in this directory, with their `.txt` outputs.

| Forced termination boundary | Broker and database outcome |
| --- | --- |
| After scheduling SQL commit, before request offset commit | One job/inbox already exists; offset absent; restarted consumer receives the same record and commits offset 1 without another job/inbox |
| After request offset commit | Offset 1 survives; restarted consumer receives the next event at offset 1 and commits offset 2; two event receipts still reference one job |
| After completion broker acknowledgement, before outbox mark | Event exists at broker offset 0, outbox remains pending; restarted publisher sends the same event ID at offset 1 and commits one published row |
| After outbox mark transaction commits | One broker record and published row survive; restarted publisher finds no pending work and sends nothing |

Each test uses a new one-partition topic and consumer group in the guarded
`caseflow_test_python_<32 hex>` namespace. It uses the migrated disposable
database fixture and actual worker database role. The consumer proxy delegates
subscription, polling and synchronous offset commits to the real Confluent
client. The publisher calls the real production `Runtime.send`. The wrapper
only redirects isolated topic/group identities, records a boundary and pauses
for the parent to force termination. Recovery starts a fresh Python process.

Consumer groups use a six-second session timeout so killed membership expires
within the bounded test. Production configuration is unchanged. Parent
observers inspect committed offsets without subscription, and read records by
explicit partition assignment without offset writes. Cleanup removes only the
owned group/topic after stopping owned children. No shared broker, database,
running service or production consumer group is restarted or reset.

## Detector sensitivity

The initial collection RED reported the missing probe module, retained as
`r3-worker-kafka-red.txt`. This alone is not a behavioral negative control.
After implementation, two deliberately broken variants were exercised:

- Replacing forced termination with `RELEASE` caused both before-offset and
  before-mark cases to fail with `normal exit is not crash evidence`.
- Committing the request offset before the advertised pre-commit boundary
  caused the test to fail with observed offset 1 when absence was required.

These mutations were restored before final focused and full verification.
Failed outputs/XML are retained as `r3-worker-kafka-red-normal-exit.*` and
`r3-worker-kafka-red-early-offset.*`. An independent AI-assisted read-only
review found no actionable issues in the two-file scope; it did not rerun tests.

## Reproduce and limits

With local Kafka and PostgreSQL running and ignored credentials configured:

```powershell
. ./scripts/dev-env.ps1
$env:PYTHONPATH = (Join-Path (Get-Location) 'services/worker')
services/worker/.venv/Scripts/python.exe -m pytest services/worker/tests/test_kafka_process_recovery.py -q --junitxml=output/worker-kafka.xml
```

The full worker suite additionally requires local object storage for the
earlier upload/crash scenario. It now also requires Kafka for these tests.
No AI calls or paid resources are involved. These tests exercise actual
messaging loops in owned component subprocesses, not full deployment restarts,
broker outages, sustained load or end-to-end rendering. The publisher fixture
uses a RUNNING status event and asserts outbox/event identity, not DOCX bytes.

Client semantics were checked against the
[official Confluent Python API reference](https://docs.confluent.io/platform/current/clients/confluent-kafka-python/html/index.html).
