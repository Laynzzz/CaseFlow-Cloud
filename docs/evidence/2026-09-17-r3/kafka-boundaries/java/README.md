# JVM Kafka process recovery proof

Revision at verification: cfaa52b627d443bc73279c93d56de0d0b7264d83 plus the exact source hashes in source-hashes.json. Timestamp and environment in metadata.json. Synthetic fixtures only; no cloud or model requests.

## Reproduce

From repository root, with existing local Kafka/PostgreSQL running:

```powershell
. ./scripts/dev-env.ps1
$env:CASEFLOW_KAFKA_PROCESS_TESTS = '1'
./services/case-api/gradlew.bat -p services/case-api test --tests 'dev.caseflow.documents.KafkaMessagingProcessRecoveryTest' --tests 'dev.caseflow.documents.CompletionProcessRecoveryTest' --rerun-tasks --console=plain
```

`--rerun-tasks` prevents cached results. The opt-in flag enables the seven actual Kafka process tests; DB credentials come only from inherited environment, never arguments or printed configuration. Existing SQL process tests require DB_ADMIN_PASSWORD. Final run: nine tests, zero skips/errors/failures, Gradle exit 0, 31 seconds total. New suite has seven tests; existing SQL suite has two.

## Observations

- Publisher: a child executes production JobMessaging.publish. A wrapper waits for the actual real-producer Future acknowledgement, emits topic/partition/offset/event ID, and remains alive. Parent independently observes unpublished SQL, forcibly kills the owned child (nonzero exit), rechecks unpublished SQL, and starts another JVM. The new process sends the same event ID at the next broker offset. Normal release allows production SQL commit. Independent broker read verifies offsets [0,1], same event ID and tenant/case key; one outbox row is marked published.
- Completion: a child runs production JobMessaging's consumer loop with the production CompletionHandler wrapped by Spring's annotation-aware transaction interceptor. At the real consumer commitSync call the test wrapper pauses. Parent independently verifies committed SUCCEEDED job/case, one APPLIED inbox receipt and one DOCUMENT_SUCCEEDED audit, while broker group offset is absent. Parent forcibly kills the live child (nonzero exit), verifies SQL/offset again, then starts a new child using the same group. Poll delivery records prove replay of the same event ID and topic/partition/offset. Release persists next offset 1. SQL still has one receipt and one audit.
- Normal-release publisher/completion cases exit 0, proving each paused child can finish without forced termination.
- Fault controls deliberately commit offsets before the boundary or skip handler persistence. The independent assertions reject each defect. These are explicitly test-only faults, not production feature flags.

Final raw boundary/PID/coordinate records are in green-final-kafka.xml. Existing SQL before/after-commit crash evidence is in green-final-sql.xml. Both raw outputs retain JUnit timing.

## Red/green and mutation evidence

1. red-missing-seam.txt records initial compilation failure because the existing JobMessaging did not allow injected real clients/topics. This is a test seam failure, not a behavioral regression assertion.
2. first-run.txt/xml records six passing Kafka tests after minimal constructor/client-interface changes.
3. red-omitted-publish-persistence.txt/xml records an actual behavioral negative control: temporarily replace the production outbox UPDATE's published_at=now() with published_at=NULL and run publisherNormalReleasePersistsAckWithoutDuplicate. It fails expected 1 vs actual 0 at the persisted publication assertion. Source was restored in a finally block.
4. green-focused.txt, green-kafka.xml and green-sql.xml record rerun after restoring source; all eight pass.

The two early-offset/missing-completion-persistence fault detectors execute in the final green suite and print KAFKA_CONTROL_REJECTED markers.

## Isolation and bounds

Each test owns a randomly named caseflow_test_<32 lowercase hex> database and an independently random topic/group namespace of the same shape. Names are validated before child use or cleanup. All three topics have one partition and replication factor 1. The child uses fixed loopback endpoints; no shared production group or topic is used. Parent drops only its owned database, deletes only its owned topics/groups, terminates only its own children and deletes only its own temporary Java argument file. Shared containers are never restarted. Fixture results use synthetic artifact metadata, not an object-store render.

Timeouts: JUnit 150 seconds/test; broker request/default API 10–15 seconds; sends 20 seconds; parent boundary wait 40 seconds; boundary release deadline 45 seconds; child completion wait 65 seconds; kill wait 10 seconds; normal exit wait 20 seconds; DB connect/socket/query bounds 5/10/10 seconds. Retrying a failed production operation is bounded by these outer process/test deadlines.

## Limits

This tests actual owned JVM termination and restart of production messaging methods and an actual Spring transactional handler proxy. It does not boot/restart the complete Spring Boot service, kill a Kafka/PostgreSQL server, claim broker high availability, complete an object-store document journey, or establish cloud release acceptance. Single-node local Kafka, one partition, synthetic fixtures. Compiler notes for existing unchecked code and deprecated test fixture APIs (including Kafka group listing) remain visible; there are no test failures.


## Review correction: live consumer-group cleanup

The new regression cleanupAfterAbruptConsumerDeathRemovesOwnedGroupAndTopics kills a real group member at the completion offset boundary, invokes teardown immediately, and independently checks that the exact group and topics no longer exist. It also exercises idempotent repeated teardown via JUnit AfterEach.

- red-live-group-cleanup.txt/xml: old cleanup failed with Kafka GroupNotEmptyException because forced process termination does not immediately expire broker membership. This was an actual behavioral RED run.
- The exact failed namespace, caseflow_test_17a34bb4f8154f908ac72c35438a461d, was removed explicitly after membership expiry. The shell validated its disposable-name pattern, deleted that one .consumer group and precisely its .jobs/.completions/.deadletters topics. No prefix sweep or dependency restart was performed. red-cleanup-owned-residue.txt records group deletion success; topic delete commands all exited successfully.
- Fixed cleanup retries specifically GroupNotEmptyException within a 15-second deadline (200-ms backoff), preserves other errors, independently attempts topic cleanup in finally, attempts all child/database cleanups, and attaches additional cleanup errors as suppressed exceptions.
- green-final-cleanup.txt, green-final-kafka.xml, green-final-sql.xml: nine final tests pass, including the new actual-membership-death regression. Raw KAFKA_CLEANUP_WAIT and KAFKA_CLEANUP_VERIFIED records show the retry path occurred and independent state verification succeeded.

Final source hashes supersede the earlier eight-test run, which is retained as historical proof rather than substituted for the final run.
