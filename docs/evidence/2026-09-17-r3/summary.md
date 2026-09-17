# R3 process-crash and broker-redelivery results

Observed September 17, 2026 UTC on Windows 11. This completes the bounded
[experiment declaration](experiment.md), not all R3 release gates. Five Python
and two Java process-crash scenarios passed. A separate run injected 10,000
broker redeliveries and retained one selected document, one success audit and
one worker execution. No AI provider calls or cloud resources were used.

## Revisions and environment

Baseline `e06f1f1`; Python probes committed as `12d339a`, Java probes as
`7dd82f6`, broker probe as `0b4e715`. Final worker regression and full broker
run use `0b4e7151ab850b710dd380ae4ed013c68cf210d1`; Java full regression ran at
`7dd82f6`. These commits change test infrastructure and the replay tool, not
production application behavior. The source hashes in [manifest.json](manifest.json)
bind the final integrated source to Git; the agent's earlier raw worktree hash
record is retained separately and may use Windows line endings.

Local environment: Python 3.12.10, pytest 9.1.1, psycopg 3.3.5,
confluent-kafka 2.15.1, Java 21, Gradle 9.7.1, Spring Boot 4.1.1,
PostgreSQL 18.6, Kafka 4.2.1, SeaweedFS 4.47. Docker dependencies run locally;
API and worker run on the host. Process tests create migrated databases named
`caseflow_test_<32 hex>` and use actual restricted application roles. Only
owned child processes and random fixture object keys are terminated/cleaned.

## Actual process termination

| Component / kill boundary | Observed recovery |
| --- | --- |
| Python before scheduling commit | No partial job/inbox; replay schedules once |
| Python after scheduling commit | Durable queued job/inbox survive; duplicate is harmless |
| Python before result commit | No selected artifact/success event; real lease expiry permits a higher-fenced replacement |
| Python after result commit | One artifact/success event survive; stale finalization/failure cannot change success |
| Python after S3 upload | Unselected DOCX remains unchanged; real lease expiry and higher fence select a new immutable object |
| Java before completion commit | Uncommitted status/audit/inbox roll back; replay applies one success |
| Java after completion commit | Success/audit/inbox survive; duplicate success and late failure have no second business effect |

Every child reports its boundary while still alive; the parent requires forced
termination and a nonzero exit. Python's focused suite passes nine tests: five
crash scenarios plus four isolation guards. Java adds two process scenarios.
Full regression reports contain **95 Python and 22 Java tests**, zero failures,
errors or skips. Repeating those suites does not create additional distinct
crash scenarios. The Python suite took 29.52 seconds; Gradle reported an
11-second successful build. These are test durations, not service benchmarks.

The upload case reads real object bytes, checks old/new checksums and the
selected DOCX's synthetic vendor and USD 70.00 total. Other result/completion
cases seed synthetic artifact metadata to isolate database atomicity. The
children invoke production functions/handlers; they are not entire running
FastAPI or Spring Boot deployments. See [worker details](worker-process-notes.md)
and [Java task record](r3-java-process-task-report.md).

Negative controls were restored before final verification. Replacing process
termination with a normal IPC release failed both Python scheduling cases and
both Java cases. Forcing Java rollback made the after-commit durability test
fail. Preserved failed runs establish that these assertions detect those faults;
they do not enumerate all possible implementation faults.

## Broker experiment

The smoke run passed with 20 duplicates plus one late failure. The subsequent
full run lasted **73.187 seconds**, from `03:58:30.237233Z` to
`03:59:43.422714Z`. It used one existing successful synthetic document job:
`a7b403e6-e3ea-45d0-9ab3-351b9c8e1f20`. Fixture and event payload hashes are
retained in the report. Source events were validated as published and previously
consumed; request and success event IDs are reused for duplicates.

| Topic, partition 1 | Records acknowledged | First / last offsets | Required / observed next committed offset |
| --- | ---: | --- | --- |
| caseflow.jobs.v1 | 5,000 request duplicates | 617 / 5616 | 5617 / 5617 |
| caseflow.completions.v1 | 5,000 success duplicates + 1 late failure | 1213 / 6213 | 6214 / 6214 |

All **10,001 unique topic/partition/offset coordinates** are retained in
[redelivery-10000.json](redelivery-10000.json). No callback errors or unflushed
records remained. The probe inspected offsets for the two production consumer
groups without subscribing, joining, committing or resetting offsets itself.
Both groups caught up, baseline equals final, every assertion passed, and the
fresh late-failure receipt is `STALE`.

The selected artifact identity and stored checksum/length remained unchanged:
SHA-256 `101540f5422116a11c724036fef5cae6ff42680f96362e9acee5cd73f1918bc8`,
36,963 bytes. Worker execution count, selected artifact count and success audit
count stayed one; failure audits stayed zero. This broker probe checks stored
object metadata, not a fresh download. Actual object-byte verification belongs
to the separate upload/crash test described above.

This is one completed job, one local broker and one partition per topic. It is
not 10,000 distinct purchases, concurrent crash injection, a sustained mixed
workload benchmark, broker high availability or exactly-once transport.

## Reproduce

Use the repository's local setup and seeded document journey from README.
Process suites require PostgreSQL; the worker upload scenario additionally
requires local S3. Broker replay requires the running API, worker and Kafka,
and `infrastructure/local/generated/document-demo.json` from the document
journey. Load ignored credentials without printing them:

```powershell
. ./scripts/dev-env.ps1
$env:PYTHONPATH = (Join-Path (Get-Location) 'services/worker')
New-Item -ItemType Directory -Force output | Out-Null
services/worker/.venv/Scripts/python.exe -m pytest services/worker/tests/test_process_recovery.py -q --junitxml=output/worker-process.xml
services/worker/.venv/Scripts/python.exe -m pytest services/worker/tests -q --junitxml=output/worker-full.xml
./services/case-api/gradlew.bat -p services/case-api test --rerun-tasks --console plain
services/worker/.venv/Scripts/python.exe services/worker/tools/replay_document.py --count 10 --timeout 180 --output ("output/redelivery-smoke-" + [guid]::NewGuid() + ".json")
services/worker/.venv/Scripts/python.exe services/worker/tools/replay_document.py --count 5000 --timeout 600 --output ("output/redelivery-10000-" + [guid]::NewGuid() + ".json")
```

`--rerun-tasks` forces execution rather than Gradle cache reuse. Replay count is
per topic, the timeout bounds the run, and output must be a new filename to
preserve previous evidence. Offsets/PIDs/random database names will differ on
rerun. Verify actual test counts and absence of skips, `PASSED`, exact counts,
consumer offsets beyond all sent records and unchanged business state.

## Evidence and review

- [Full worker output](worker-full.txt) and [JUnit](worker-full.xml); [focused process output](worker-process.txt) and [JUnit](worker-process.xml).
- [Full Java output](java-full.txt); `TEST-*.xml` in this directory contains the six suites, including [process boundaries/PIDs](TEST-dev.caseflow.documents.CompletionProcessRecoveryTest.xml).
- [Python normal-exit failure](worker-negative-control.txt); [Java normal-exit failure](r3-java-process-red-normal-exit.xml) and [missing-commit failure](r3-java-process-red-missing-commit.xml); restored `r3-java-*-green*.xml` reports are retained.
- [Broker smoke](redelivery-smoke.json), [full run](redelivery-10000.json), corresponding `.txt` outputs and [tool task record](r3-broker-task-report.md).
- [Independent review scope](review.md), source/artifact hashes in [manifest.json](manifest.json).

Text artifacts are archived with LF line endings and trailing whitespace removed
from Markdown/plain text; XML hostnames are replaced with `local-test-host`.
No test results, PIDs, event coordinates or timestamps
are changed. Agent reports referring to `output/r3-*` describe their original
capture locations; those files are archived here with the same basenames.
The smoke script hash reflects its CRLF working copy; the full run hash matches
exact LF Git bytes at `0b4e715`. Hashes embedded in original reports are preserved.
The manifest hashes the archived bytes, excluding the manifest itself.

## Remaining gates

Publisher/offset crash windows, dependency restarts during active work, object
store timeouts, reconciliation/orphan collection, measured query optimization,
sustained mixed load, tracing/metrics/alerts, cloud smoke/rollback/teardown and
clean-checkout portfolio work remain open in [the R3 map](../../r3-status.md).
R2's extraction-quality limitation and R1 cloud gap remain unchanged. The USD 10
AI ledger remains at USD 0.633975 accounted; this batch consumed no AI budget.
