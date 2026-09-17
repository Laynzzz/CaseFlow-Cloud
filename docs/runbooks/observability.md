# Local metrics, traces and recovery alerts

For an approved purchase, a fast HTTP response only means the command was
accepted. The document can still be queued, executing, waiting for publication
or waiting for the Java completion consumer. This monitoring profile separates
those signals so an operator can locate a delay without reading purchase text.

The overlay is [`compose.observability.yaml`](../../compose.observability.yaml).
It adds the OpenTelemetry Collector, Prometheus, Tempo and provisioned Grafana
to the isolated `caseflow-release` Compose project. It uses the release
project's default network and never points at the development database or
consumer groups. Application instrumentation and actual demonstration evidence
are separate from successful configuration validation.

## Start and inspect

From the repository root, with Docker Desktop running, choose a new release
name. The release helper generates ignored local credentials, builds immutable
application images, starts dependencies and performs its release smoke:

```powershell
node scripts/release.mjs build r3-observed
node scripts/release.mjs deploy r3-observed --observability
node scripts/release.mjs status
```

The monitoring images are pinned by tag and registry digest. See
[`versions.json`](../../infrastructure/observability/versions.json) for official
release sources and the verification date. No hosted monitoring account or
model call is used.

| Local endpoint | Purpose |
| --- | --- |
| [Grafana](http://127.0.0.1:13000/d/caseflow-operations) | Provisioned 22-panel operations dashboard and Tempo Explore |
| [Prometheus targets](http://127.0.0.1:19090/targets) | API, worker and collector scrape availability |
| [Prometheus alerts](http://127.0.0.1:19090/alerts) | Pending/firing recovery rules |
| [Tempo readiness](http://127.0.0.1:13200/ready) | Trace storage/query service health |
| `http://127.0.0.1:14318/v1/traces` | OTLP/HTTP receiver for explicitly scoped local evidence |

Prometheus scrapes `api:9091/actuator/prometheus`, `worker:8090/metrics` and
`otel-collector:8888/metrics` every 15 seconds with a ten-second deadline.
The SQL/Kafka metrics report collection availability separately; absence of
observations is not a healthy zero backlog. Gauge series may be absent when
there are no corresponding durable jobs or AI calls.

All host ports bind only to `127.0.0.1`. Grafana uses anonymous **Viewer** access
with login, sign-up and initial administrator creation disabled. Dashboards
and data sources come from versioned provisioning files. This is a synthetic,
local viewing profile. Exposing it beyond loopback requires an authenticated
deployment design. Grafana and Tempo usage reporting are disabled.

## Sampling, data minimization and correlation

The default root sampling probability is `CASEFLOW_TRACE_SAMPLE_RATE=0.1`.
Application propagation preserves a sampled parent decision across outbox,
Kafka, durable job execution and completion. For a bounded synthetic evidence
run only, deploy with `1.0`, record that choice, then redeploy with `0.1`:

```powershell
$env:CASEFLOW_TRACE_SAMPLE_RATE = '1.0'
node scripts/release.mjs deploy r3-observed --observability
# Run the authorized synthetic scenario and capture evidence.
$env:CASEFLOW_TRACE_SAMPLE_RATE = '0.1'
node scripts/release.mjs deploy r3-observed --observability
```

Sampling at 1.0 requests full recording for that bounded run; it does not
guarantee universal export. Collector memory, export retries, application
shutdown, unavailable storage or ingestion limits can still lose telemetry.
Do not treat a trace as the durable business record. Database status, inboxes,
outboxes and audit remain the authority.

The collector accepts traces only. Its allowlist retains service identity,
HTTP method/status/template route, job kind and fixed outcome. It removes
URL/query/header/authorization/business attributes, status descriptions and
tracestate, drops span events containing possible exception text, and replaces
unknown names. Fixed custom operations are `api.publish`, `api.complete`,
`worker.schedule`, `worker.execute` and `worker.publish`. HTTP names are rebuilt
from the instrumentation's route template and method; UUID path fragments are
normalized and query suffixes removed. Route attributes must come from server
instrumentation, never client request bodies.

The first integrated Java trace used Micrometer attribute names outside this
allowlist, so automatic HTTP/security spans appeared as `caseflow.operation`
without route attributes. The five fixed application operations still identify
the asynchronous path and parent relationships. HTTP route/latency metrics are
separate and remain available. An explicit, tested mapping for Micrometer route
attributes is future work; broadening the allowlist during a load run would
invalidate that run's configuration provenance.

Trace/span/parent IDs remain intact for parent-based correlation. Current
instrumentation does not create span links. The pinned collector drops any
span containing links because their attributes cannot be scrubbed by this
pipeline; link-based instrumentation needs a reviewed extension. The collector
drops a batch on transformation error instead of exporting unprocessed content.
There is no raw-content debug exporter in the deployed profile.

Worker metric labels are bounded job kinds/statuses/outcomes/services. Kafka
lag observes only two fixed topic/group pairs using read-only admin operations.
Tenant, case, job, event, actor and trace IDs are not metric labels. Prometheus
also drops common identity/URL/auth label names as defense in depth. This is
not permission to put content in any other label.

## Metrics target or database unavailable

For `CaseflowMetricsTargetDown`, identify the target on the Prometheus targets
page and check container state with `node scripts/release.mjs status`. A failed
API scrape can be a management-port or service problem; a failed worker scrape
can be a process or collection-timeout problem. Collector availability does not
by itself prove successful Tempo export.

For `CaseflowMetricsDatabaseUnavailable`, inspect the worker's metadata-only
logs for connectivity/timeouts, then check the release PostgreSQL health.
Do not export environment variables, connection strings, credentials or raw
exception objects into an incident report. Recover connectivity and verify
the gauge becomes one and durable queue metrics resume. Do not declare an
empty queue from a failed database observation.

## Old jobs, outbox or expired leases

`CaseflowReadyJobOld` starts pending when the oldest ready job exceeds 120
seconds and fires after another two minutes. `CaseflowOutboxOld` uses an age
over 60 seconds for two minutes. `CaseflowExpiredLease` requires at least one
expired lease for one minute. These are initial local demonstration thresholds,
not measured production SLOs.

Compare queue age, execution duration, worker retry counters, outbox age and
Kafka lag. Old ready work with healthy publication suggests dispatch/execution
capacity or unavailable inputs. Growing outbox age suggests broker/publisher
trouble. Expired leases indicate lost execution ownership and should be
reclaimed through the normal fenced lease protocol. Use the repository's
metadata-only reconciliation procedure for exact job diagnosis; do not update
job status, fences or offsets by hand. Restore dependencies first, and use an
authorized audited retry only for an eligible failed job. Confirm one selected
result and one visible completion after recovery.

## Kafka lag and telemetry export

`CaseflowKafkaMetricsUnavailable` distinguishes a failed lag observation from
zero lag. `CaseflowKafkaConsumerLag` fires for a fixed consumer pair over 100
records behind for two minutes. Correlate lag with arrival rate and durable
queue growth: rising lag with a flat arrival rate suggests the relevant
consumer is stopped, retrying a record or throughput limited. Do not advance
offsets to hide backlog. Check the consumer's metadata logs and restore its
dependency; poison records follow the dead-letter procedure below.

If a known sampled trace is absent, inspect collector and Tempo availability,
then metadata-only exporter failure logs. Collector buffering is bounded and
retry time is at most 60 seconds. The monitoring profile has no persistent
collector export queue. A restart or prolonged backend outage may lose spans
while the business job correctly survives. Reproduce a new authorized
synthetic operation to establish restored export; do not repeat costly AI
operations merely to obtain a trace.

## Repeated failures and dead letters

`CaseflowRepeatedFailures` uses more than three worker retry/validation/
dependency/lease-renewal failures over five minutes, sustained for 30 seconds.
`CaseflowDeadletterObserved` reports any increment of the worker's acknowledged
dead-letter counter. Duplicate dead letters can be normal after a crash in the
acknowledgement/offset gap; they do not imply duplicate business effects.

Use [the dead-letter runbook](deadletter-recovery.md) and preserve original
broker coordinates during authorized diagnosis. It deliberately provides no
arbitrary JSON replay command. Validation failures require source correction;
transient dependency failures can recover through the normal retry policy.

## Latency and saturation

`CaseflowHttpLatencyHigh` fires when the five-minute API HTTP p95 exceeds one
second for two minutes. Inspect HTTP rate/errors, Hikari active/pending
connections and committed/rolled-back transaction counters. Then inspect job
queue and execution histograms independently. Queue and execution p95 are not
end-to-end document completion latency, and quantiles cannot be added.

The dashboard exposes lifetime AI actual/reserved cost and tokens from durable
ledger states. Unknown billing remains visible; the shared USD 10 ceiling is
not reset by a new monitoring session. Reading these gauges makes no model call.

Each rule has a `runbook_url` annotation naming this file and its relevant
section. These are repository-relative references for workspace navigation;
Prometheus does not serve repository Markdown. Alerts are evaluated/displayed
locally; no Alertmanager or external notification destination is configured.

## Validate, retain evidence and stop

Validate collector/Prometheus/Tempo configuration with their pinned container
binaries. The collector privacy verifier also exercises real OTLP ingestion
and file export with synthetic sentinels, using an owned container and random
loopback port; it does not contact the application or model:

```powershell
py -3.12 infrastructure/observability/verify-collector.py --output output/collector-privacy
node scripts/release.mjs stop
```

The verifier is a configuration/privacy test, separate from the full
API-to-worker trace and diagnosed-failure demonstration. Its successful result
must preserve parent IDs, retain fixed names, remove denied content/events and
drop the intentionally unsupported linked span. Failed probe logs should be
preserved. Static collector validation alone cannot catch every runtime OTTL
type error; the actual ingestion check caught one during implementation.

Prometheus retains at most 24 hours or 1 GB of samples. Tempo's local trace
storage uses its pinned default 14-day retention; neither limit is a hard host
disk or memory spending cap. Named monitoring volumes survive `stop` and
normal deployment/rollback. Preserve release evidence before intentionally
removing monitoring data. Do not use `down -v` as a routine stop: the combined
project also contains the product database and object store.

## Official references

- [Collector transformation and failure behavior](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.161.0/processor/transformprocessor/README.md)
- [Collector filtering](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.161.0/processor/filterprocessor/README.md)
- [Tempo single-binary example](https://github.com/grafana/tempo/blob/v3.0.3/example/docker-compose/single-binary/tempo.yaml)
- [Prometheus alert rules and local inspection](https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/)
- [Grafana file provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/)
