# Local sustained manual-document self-test — 2026-09-17

**Observed result: passed at this bounded operating point.** A 30-second warmup
followed by 180 seconds at 2 mixed arrivals/second completed all 84 real DOCX
jobs, with no HTTP errors, dropped iterations, failed jobs, or remaining backlog.
This is one short local experiment, not a maximum-capacity or cloud claim.

## Workload and environment

- Command: `node tests/load/run.mjs`, with
  `LOAD_TRACE_SAMPLE_RATE='1.0 (100 percent; coordinated bounded trace evidence)'`.
  Other harness settings used their documented defaults.
- Exact environment, source SHA-256 values, revision and dirty paths:
  [environment.json](environment.json). Base checkout revision was
  `926f4fdd4f13059cce961edf1876ffe56457069f`; the working-tree hashes identify
  the precise workload files used. The full k6 version was
  `k6.exe v2.2.0 (commit/00a9a1b7f5, go1.26.5, windows/amd64)`.
- Two fresh synthetic tenants, ten seed drafts each, equal tenant distribution,
  fixed 80% read / 20% approval mix, USD 4,200 laptop payload, two approval steps.
  Version `synthetic-manual-purchase-load-v1`, fixed seed marker 20260917.
  [Fixture IDs and payload](fixtures.json) are retained. No provider calls.
- Windows 10.0.26200, Intel i7-13700K, 24 logical CPUs, approximately 31.74 GiB
  host RAM; Docker Desktop was shared with existing local services. No service
  was deleted or stopped for this run. Dataset seeding and warmup warmed caches.
- The Java and Python containers each had a 768 MiB memory limit and no explicit
  CPU quota. [container-images.txt](container-images.txt) records all actual
  immutable image IDs and resource limits. API image:
  `sha256:87a44e850c5453ed5600d633e39ecb65bb17470a04457618888fb39380b16c60`;
  worker image:
  `sha256:00b022975f90d6baeb85854253632bb4be867b2244a49dfc24ec066689c668c3`.
  The [application release manifest](application-release.json) records the
  actual image-build checkout `de03e248cf708fed102b1100648b6e12057e0660`, dirty
  build source digest
  `5bb9ec613886acda097d597f4e62e771a033850eae6b240a6e41593466d42dc8`.
  This is distinct from the later harness checkout revision; neither is
  misrepresented as a clean source build.
- Trace sampling was explicitly 100% for this bounded evidence window. The
  independent completion observer, metric scrapes and local credential bridge
  add overhead; they were not counted as business acknowledgement requests.

## Measurements

| Measurement | Observed value | Source |
| --- | --- | --- |
| Total mixed iterations | 420: 336 read journeys, 84 approval journeys | k6 summary |
| Measured phase | 288 reads + 72 approvals in 180 seconds | phase counters |
| Business HTTP requests | 1,092 total; 936 measured | k6 application counters |
| Measured HTTP acknowledgement p50 / p95 / p99 | 4.876 / 10.458 / 14.604 ms | `application_http_ack_ms{phase:sustained}` |
| Measured final-approval acknowledgement p95 | 7.415 ms | `final_approval_ack_ms{phase:sustained}` |
| HTTP errors / iteration errors / dropped iterations | 0 / 0 / 0 | k6 thresholds |
| Extra offers refused at exact iteration budget | 0 | `arrival_budget_refusals` |
| Documents completed | 84/84, including all 72 measured-phase jobs | API observer |
| Measured-cohort completion p50 / p95 / max | 2.664 / 3.835 / 3.950 s | final acknowledgement → observed `SUCCEEDED` |
| Queue mean; cumulative bound | 264.46 ms; 82/84 ≤500 ms, all ≤1 s | worker histogram delta, includes warmup |
| Execution mean; cumulative bound | 43.69 ms; all 84 ≤100 ms | worker histogram delta, includes warmup |
| Pending jobs over 106 observer snapshots | maximum 2; final 0 | backlog.json |
| Last completion observed after arrivals stopped | 2.342 s | job timestamps versus generator exit |
| Observer work | 153 requests of the 1,200-request cap | result.json |
| Reconciliation before / after drain | `NO_FINDINGS` / `NO_FINDINGS` at 60-second age threshold | reconciliation snapshots |
| Download verification | 2/2 samples: SHA-256, size, ZIP signature, outsider denial | downloads.json |

All k6 thresholds passed. The raw `http_req_failed` rate is zero; k6's `passes`
and `fails` fields on that rate metric count true and false samples respectively,
so `fails: 1092` means 1,092 requests whose failure predicate was false.
Likewise, k6 phase-counter rates use the whole 210-second scenario denominator;
use the recorded phase counts and 180-second phase duration when discussing the
measured offer rate. The nominal document offer rate was 0.4/s.

Completion latency includes observer delay from two-second polling, not just
execution. Queue and execution values above are before/after histogram deltas,
with exact means from sums/counts and **bucket bounds**, not invented exact
percentiles. The after-warmup snapshot can support a separate interval delta,
but jobs can straddle that boundary. Fast acknowledgement alone is insufficient;
here the bounded backlog and final drain also succeeded.

## Resource and saturation observations

Both configured Kafka topic/group pairs showed lag zero at all five collection
points. Database and Kafka collector health were one at each collection. The
midpoint API pool had one active, four idle, zero pending connections, and a
five-connection maximum. This is sampled evidence, not proof that no transient
lag or pool wait occurred between samples.

Across five Docker point samples, API CPU reached 2.39% and memory 424.1 MiB of
768 MiB; worker CPU reached 22.45% and memory 97.87 MiB of 768 MiB. PostgreSQL
CPU reached 2.61% and memory 59.82 MiB. Kafka had a 175.78% CPU sample and a
514.9 MiB memory sample. Docker CPU percentages can exceed 100% across cores;
these point samples do not establish peak saturation or attribute a spike's
cause. Raw snapshots and exact collection times remain available.

k6 reported an allocated maximum of ten VUs, zero dropped iterations, and a
`vus` summary gauge of zero. The latter is retained as emitted; it is not used
as evidence that the generator used no concurrent workers. No saturation test
or increasing-rate search was performed.

## Integrity, limitations and supporting files

The three required negative fixture-access checks ran and returned 404; they
were not skipped. Both sample downloads also denied the outsider. These checks
support this workload's fixture isolation and do not replace the full tenant
security suite. The sample DOCX files validate byte integrity; the release smoke
separately parses Word contents. No credentials or tokens are included here.

Raw sources: [k6-summary.json](k6-summary.json), [result.json](result.json),
[jobs.json](jobs.json), [backlog.json](backlog.json),
[worker-histograms.json](worker-histograms.json),
[downloads.json](downloads.json), [authorization.json](authorization.json),
[infrastructure-snapshot-times.json](infrastructure-snapshot-times.json).
Raw Prometheus snapshots are retained as lossless `*.prom.gz` files. Their
decompressed and normalized gzip SHA-256 values are in
[raw-artifacts.json](raw-artifacts.json). The exact five workload source files
are in [workload-source.tar.gz](workload-source.tar.gz), with normalized archive
and per-file hashes in [workload-source-manifest.json](workload-source-manifest.json).
Normalized tar SHA-256:
`9afad8cd117d3453509ee7221fc3bc933b3c694ceb0678e68824f02a8e89ba8b`;
normalized gzip SHA-256:
`6185c9708346dd4831bed24f04d3cee4ea13527b45c9b29e5f72df1a6e837191`.
Archive normalization sorts names, sets uid/gid/mtime to zero, uses mode 0644,
empty owner names and gzip mtime zero. Decompression restores the exact measured
workload and raw metric bytes; it is not a regenerated benchmark.
The preceding [ten-second probe](../2026-09-17T15-02-55-071Z/result.json) passed
4/4 documents but is explicitly a harness check. That probe exposed one extra
k6 duration-boundary iteration; the sustained version adds a counted refusal
before any business work beyond its exact budget. Probe artifacts are preserved.

This demonstrates a reproducible local operating point with real completion and
bounded queues. It does not establish long-duration stability, maximum
sustainable throughput, cloud delivery, production adoption, AI throughput,
or performance on the separate large/skewed SQL benchmark dataset.
