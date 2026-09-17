# Correlated telemetry and operational endpoints

Verified 2026-09-17 on Windows with Docker Desktop dependencies and isolated Linux
release containers. Parent revision de03e24 plus the source changes in this
telemetry commit; packaged candidate manifest records its source fingerprint.
No provider calls or AWS resources. 42 Java and 169 Python tests pass with zero
failures/skips. Focused added contracts: trace-parent durability, secret/baggage
exclusion, private-management access, unavailable collection, lease-reclaim timing,
export opt-in and bounded Kafka offset reads. JUnit XML and raw run logs are here.

Commands (PowerShell, repository root):

```powershell
. ./scripts/dev-env.ps1
$env:CASEFLOW_KAFKA_PROCESS_TESTS='1'
$env:CASEFLOW_QUERY_BENCHMARK='1'
./services/case-api/gradlew.bat -p services/case-api test --rerun-tasks --console plain
$env:PYTHONPATH=Join-Path (Get-Location) 'services/worker'
services/worker/.venv/Scripts/python.exe -m pytest services/worker/tests -q --tb=short
```

Suites ran serially. Missing-feature compile/import failures preceded implementation.
A Windows Java process-command length failure after SDK expansion was fixed by
passing the subprocess classpath in a file instead of a huge JVM system property.
The expanded recovery suites pass with that fix. An initial trace test identified
new W3C random trace flags; sanitization now accepts valid two-digit flags while
still rejecting invalid IDs and baggage. Neither issue is hidden by test retries.

## Actual exported trace

`actual-trace.json` was retrieved by trace ID from the local Tempo backend after
`node scripts/release.mjs deploy telemetry-candidate --observability` passed the
full PKCE/approval/DOCX smoke. Trace 9ffaa7f899394e2a8dd162504b0c9db1 includes both
services: API request ancestry → api.publish → worker.schedule/worker.execute →
worker.publish → api.complete. RUNNING and SUCCEEDED completion publications are
distinct spans in that trace. All spans share the same trace ID; completion parents
match the worker publication IDs. Generic framework spans are intentionally named
`caseflow.operation` by the collector privacy filter; explicit business operations
remain named. Raw URL, query, authorization, business content and exception events
are excluded. This run uses explicitly configured 100% sampling; default is 10%.

Actual metrics reads: API and worker endpoints return 200 only on their operational
listeners; the public API denies actuator reads. All three Prometheus targets are
up. Worker database/Kafka collection signals are 1; both fixed consumer group lags
are 0. The smoke produced one document queue/execution histogram observation and
API transaction-commit counts. No job/tenant/case IDs are metric labels.

## Limits

Queue time starts at due time (or expired lease for reclaim), not original creation;
intentional retry backoff is excluded. End-user completion latency is separate.
Execution timing includes result persistence. AI ledger metrics are durable lifetime
sums with unknown calls kept reserved, not zero-cost assumptions or new live tests.
Kafka lag is a bounded read snapshot, not a queue/throughput guarantee. Metrics
collection can fail; it reports unavailable and omits fictitious backlog/lag values.

This evidence is not sustained-load, alert-recovery or AWS evidence. Those gates
are separately recorded. Collector privacy runtime checks live in the monitoring
batch; forwarding via arbitrary span links is not supported by that local profile.

Primary implementation references checked for the pinned versions:
[Spring Boot tracing](https://docs.spring.io/spring-boot/reference/actuator/tracing.html),
[OpenTelemetry Python exporters](https://opentelemetry.io/docs/languages/python/exporters/),
[Prometheus Python](https://prometheus.github.io/client_python/),
[Confluent AdminClient](https://docs.confluent.io/platform/current/clients/confluent-kafka-python/html/index.html).
