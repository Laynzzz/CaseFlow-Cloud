# Dead-letter process recovery evidence — 2026-09-17

Four distinct local poison-envelope process-crash scenarios passed: two Python
and two Java. These extend the earlier thirteen business-boundary scenarios;
normal recovery subprocesses, repeated runs and cleanup are not extra crash
scenarios. R3's separate deployment, tracing, sustained-load and cloud gates are
not established by these tests.

| Component | Actual forced-kill boundary | Observed recovery |
| --- | --- | --- |
| Python worker | Before dead-letter producer submission | Original source coordinate replayed; one redacted dead letter; source offset commits after acknowledgement |
| Python worker | After real dead-letter acknowledgement, before source-offset commit | Original source coordinate replayed; identical diagnosis at two distinct dead-letter offsets; source offset then commits |
| Java completion consumer | Before dead-letter producer submission | Original source coordinate replayed; one redacted dead letter; source offset commits after acknowledgement |
| Java completion consumer | After real dead-letter acknowledgement, before source-offset commit | Original source coordinate replayed; identical diagnosis at two distinct dead-letter offsets; source offset then commits |

Every case observes the live owned child at the intended boundary, forcibly
terminates it, requires nonzero exit and starts a new child for recovery.
The production Python `Runtime.consume` and Java `JobMessaging` loops handle
the synthetic invalid record. Both consumers use real Kafka clients against
loopback Kafka, random single-partition topics/groups and migrated disposable
PostgreSQL databases. No running application is killed and no demo data is
modified. These tests require zero business database effects for invalid
records, exact dead-letter field allowlists, correct original coordinates and
digest, and absence of the synthetic private-content sentinel in dead letters
and evidence.

The before-submission boundary establishes an interruption before publishing;
it does not simulate packet loss or publication already in flight. The
after-acknowledgement boundary proves expected duplicate redacted diagnoses
under at-least-once handling. There is no claim of exactly-once transport or
automatic correction of invalid business references.

## Actual results

- Final Python focused run: **2 passed**, 15.54 seconds console / 15.435 seconds
  JUnit; zero failures, errors or skips. See `python-final.txt` and
  `python-final.xml`. Initial passing evidence remains in `python-focused.*`;
  the final rerun follows an assertion-only change preventing sentinel
  disclosure in a failed assertion message.
- Java focused run: **2 passed**, 16.754 seconds JUnit / Gradle build 19 seconds;
  zero failures, errors or skips. See `java-focused.txt` and
  `java-focused.xml`. Both forced JVM exits were 1, both restart exits were 0.
- Both languages leave source offset 0 uncommitted at the crash boundary and
  commit next offset 1 after recovery. The before-submission cases have one
  dead letter after recovery; after-acknowledgement cases have two. Every
  dead letter is checked for metadata-only content and source coordinate 0.
- No AI calls, budget changes, paid cloud actions or dependency restarts.

`source-manifest.json` records the baseline revision, worktree-byte source
hashes, artifact hashes and mechanically extracted test totals/timestamps.
Only the focused suites were run by this task. Existing Java deprecation and
unchecked warnings remain visible in the raw Gradle output. Integration/full
suite validation belongs to the parent R3 work.

## Reproduce and operate

Commands and guarded recovery guidance are in
[`docs/runbooks/deadletter-recovery.md`](../../../runbooks/deadletter-recovery.md).
The Java tests must be explicitly enabled with
`CASEFLOW_KAFKA_PROCESS_TESTS=1`; skips do not count as evidence. The environment
loader reads ignored credentials without printing them. Retain source topic,
partition, offset and digest during authorized diagnosis; use existing business
commands or eligible audited job retry after correcting the cause. No arbitrary
payload replay or live group offset reset is provided.

Both helper implementations are test-only and preserve production methods.
Python reuses `BrokerFixture`, endpoint/identity guards and client options.
Java reuses `KafkaMessagingCrashProbe` client options and
`CompletionCrashProbe` database guards/handler. New helper/test files are
separate from prior crash fixtures and the production messaging runtime.

Archive normalization: LF endings and trimmed trailing whitespace. The archive manifest records original and normalized hashes. Full integration subsequently passed 42 Java and 169 Python tests in the telemetry batch; the Java child classpath now travels through a file to avoid Windows process limits.
