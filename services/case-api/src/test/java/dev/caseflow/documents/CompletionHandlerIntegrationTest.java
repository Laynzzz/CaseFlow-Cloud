package dev.caseflow.documents;

import dev.caseflow.common.Commands;
import dev.caseflow.common.Json;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.DriverManager;
import java.time.Duration;
import java.util.Comparator;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.jdbc.support.JdbcTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import tools.jackson.databind.json.JsonMapper;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTimeoutPreemptively;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** Real disposable SQL database; synthetic completion fixtures, never the running demo. */
@EnabledIfEnvironmentVariable(named = "DB_ADMIN_PASSWORD", matches = ".+")
class CompletionHandlerIntegrationTest {
    private static final String INPUT_HASH = "a".repeat(64);
    private static final String ARTIFACT_HASH = "b".repeat(64);

    private String databaseName;
    private JdbcTemplate admin;
    private JdbcTemplate observer;
    private JdbcTemplate db;
    private TransactionTemplate tx;
    private CompletionHandler handler;
    private UUID tenant;
    private UUID caseId;
    private UUID jobId;
    private UUID actor;

    @BeforeEach
    void setup() throws Exception {
        databaseName = "caseflow_test_" + UUID.randomUUID().toString().replace("-", "");
        try (var connection = DriverManager.getConnection(
                "jdbc:postgresql://127.0.0.1:54320/caseflow", "caseflow_admin", System.getenv("DB_ADMIN_PASSWORD"))) {
            connection.createStatement().execute("CREATE DATABASE " + databaseName + " OWNER caseflow_migrator");
        }
        admin = new JdbcTemplate(new DriverManagerDataSource(
                jdbcUrl(), "caseflow_migrator", System.getenv("DB_MIGRATOR_PASSWORD")));
        observer = new JdbcTemplate(new DriverManagerDataSource(
                jdbcUrl(), "caseflow_admin", System.getenv("DB_ADMIN_PASSWORD")));
        try (var files = Files.list(Path.of("../../db/migrations"))) {
            for (var path : files.filter(p -> p.getFileName().toString().matches("V\\d+__.*\\.sql"))
                    .sorted(Comparator.comparingInt(p -> Integer.parseInt(
                            p.getFileName().toString().split("__")[0].substring(1))))
                    .toList()) {
                admin.execute(Files.readString(path));
            }
        }

        var apiDataSource = new DriverManagerDataSource(
                jdbcUrl(), "caseflow_api", System.getenv("DB_API_PASSWORD"));
        db = new JdbcTemplate(apiDataSource);
        tx = new TransactionTemplate(new JdbcTransactionManager(apiDataSource));
        var json = new Json(JsonMapper.builder().build());
        handler = new CompletionHandler(db, new Commands(db, json));

        tenant = UUID.randomUUID();
        caseId = UUID.randomUUID();
        jobId = UUID.randomUUID();
        actor = UUID.randomUUID();
        admin.update("INSERT INTO core.identities(id,issuer,subject,display_name) VALUES (?,'https://synthetic-tests.invalid',?,'Synthetic requester')",
                actor, actor.toString());
        admin.update("INSERT INTO core.tenants(id,name) VALUES (?,'Isolated completion test')", tenant);
        admin.update("INSERT INTO core.memberships(tenant_id,user_id,roles) VALUES (?,?,ARRAY['REQUESTER'])",
                tenant, actor);
        admin.update("INSERT INTO core.cases(tenant_id,id,owner_id,state,purchase,approved_at,document_status,generation_id) "
                        + "VALUES (?,?,?,'APPROVED','{}'::jsonb,now(),'QUEUED',?)",
                tenant, caseId, actor, jobId);
        admin.update("INSERT INTO core.job_requests(tenant_id,job_id,case_id,kind,input,input_hash,requested_by,status) "
                        + "VALUES (?,?,?,'DOCUMENT','{}'::jsonb,?,?,'QUEUED')",
                tenant, jobId, caseId, INPUT_HASH, actor);
        admin.update("INSERT INTO worker.jobs(tenant_id,job_id,case_id,kind,attempt,input_hash,status,fence) "
                        + "VALUES (?,?,?,'DOCUMENT',1,?,'SUCCEEDED',1)",
                tenant, jobId, caseId, INPUT_HASH);
        admin.update("INSERT INTO worker.artifacts(tenant_id,job_id,attempt,fence,object_key,sha256,byte_size) "
                        + "VALUES (?,?,1,1,?,?,128)",
                tenant, jobId, "synthetic/completions/" + jobId + "/1.docx", ARTIFACT_HASH);
    }

    @AfterEach
    void cleanup() throws Exception {
        if (databaseName != null) {
            assertTrue(databaseName.matches("caseflow_test_[a-f0-9]{32}"));
            try (var connection = DriverManager.getConnection(
                    "jdbc:postgresql://127.0.0.1:54320/caseflow", "caseflow_admin", System.getenv("DB_ADMIN_PASSWORD"))) {
                connection.createStatement().execute("DROP DATABASE " + databaseName + " WITH (FORCE)");
            }
        }
    }

    @Test
    void appliesSuccessAtomically() {
        apply(success(UUID.randomUUID()));

        assertBusinessSuccess();
        assertEquals(1, count("SELECT count(*) FROM core.event_inbox WHERE disposition='APPLIED'"));
        assertEquals(1, count("SELECT count(*) FROM core.audit WHERE event_type='DOCUMENT_SUCCEEDED'"));
    }

    @Test
    void rollsBackBeforeCommitThenReplaysAndClassifiesDuplicates() {
        UUID eventId = UUID.randomUUID();
        var completion = success(eventId);

        assertThrows(IllegalStateException.class, () -> tx.executeWithoutResult(status -> {
            handler.apply(completion);
            throw new IllegalStateException("injected before commit");
        }));

        assertEquals("QUEUED", jobStatus());
        assertEquals("QUEUED", documentStatus());
        assertEquals(0, count("SELECT count(*) FROM core.event_inbox"));
        assertEquals(0, count("SELECT count(*) FROM core.audit"));

        apply(completion);
        apply(completion);
        apply(success(UUID.randomUUID()));

        assertBusinessSuccess();
        assertEquals(1, count("SELECT count(*) FROM core.event_inbox WHERE disposition='APPLIED'"));
        assertEquals(1, count("SELECT count(*) FROM core.event_inbox WHERE disposition='STALE' AND reason='OLDER_EXECUTION'"));
        assertEquals(1, count("SELECT count(*) FROM core.audit WHERE event_type='DOCUMENT_SUCCEEDED'"));
    }

    @Test
    void keepsSuccessTerminalWhenDelayedFailureArrives() {
        apply(success(UUID.randomUUID()));
        var failure = event(UUID.randomUUID(), tenant, 1, 1, "FAILED");

        apply(failure);

        assertBusinessSuccess();
        assertEquals(1, count("SELECT count(*) FROM core.event_inbox WHERE disposition='STALE' AND reason='OLDER_EXECUTION'"));
        assertEquals(0, count("SELECT count(*) FROM core.audit WHERE event_type='DOCUMENT_FAILED'"));
    }

    @Test
    void quarantinesFutureAttemptUnprovenFenceMissingResultAndWrongTenantWithoutMutation() {
        apply(event(UUID.randomUUID(), tenant, 2, 1, "SUCCEEDED"));
        apply(event(UUID.randomUUID(), tenant, 1, 2, "SUCCEEDED"));
        admin.update("DELETE FROM worker.artifacts WHERE tenant_id=? AND job_id=?", tenant, jobId);
        apply(event(UUID.randomUUID(), tenant, 1, 1, "SUCCEEDED"));
        apply(event(UUID.randomUUID(), UUID.randomUUID(), 1, 1, "SUCCEEDED"));

        assertEquals("QUEUED", jobStatus());
        assertEquals("QUEUED", documentStatus());
        assertEquals(0, count("SELECT count(*) FROM core.audit"));
        assertReceipt("FUTURE_ATTEMPT");
        assertReceipt("UNPROVEN_EXECUTION");
        assertReceipt("MISSING_RESULT");
        assertReceipt("UNKNOWN_JOB");
    }

    @Test
    void concurrentDuplicateCompletionHasOneBusinessEffectAndFiniteDeadline() {
        assertTimeoutPreemptively(Duration.ofSeconds(10), () -> {
            var firstHasCaseLock = new CountDownLatch(1);
            var releaseFirst = new CountDownLatch(1);
            var secondTransactionStarted = new CountDownLatch(1);
            var secondBackendPid = new AtomicInteger();
            try (var executor = Executors.newFixedThreadPool(2)) {
                UUID eventId = UUID.randomUUID();
                var completion = success(eventId);
                var first = executor.submit(() -> tx.executeWithoutResult(status -> {
                    db.queryForObject("SELECT id FROM core.cases WHERE tenant_id=? AND id=? FOR UPDATE",
                            UUID.class, tenant, caseId);
                    firstHasCaseLock.countDown();
                    await(releaseFirst, "release first completion");
                    handler.apply(completion);
                }));
                var second = executor.submit(() -> {
                    await(firstHasCaseLock, "first transaction case lock");
                    tx.executeWithoutResult(status -> {
                        secondBackendPid.set(db.queryForObject("SELECT pg_backend_pid()", Integer.class));
                        secondTransactionStarted.countDown();
                        handler.apply(completion);
                    });
                });
                try {
                    assertTrue(secondTransactionStarted.await(2, TimeUnit.SECONDS));
                    assertBackendWaitsOnLock(secondBackendPid.get());
                } finally {
                    releaseFirst.countDown();
                }
                first.get(8, TimeUnit.SECONDS);
                second.get(8, TimeUnit.SECONDS);
            }
        });

        assertBusinessSuccess();
        assertEquals(1, count("SELECT count(*) FROM core.event_inbox WHERE disposition='APPLIED'"));
        assertEquals(1, count("SELECT count(*) FROM core.audit WHERE event_type='DOCUMENT_SUCCEEDED'"));
    }

    @Test
    void rejectsUnsupportedAndMismatchedCompletionsWithoutBusinessEffects() {
        for (var change : java.util.List.of(Map.of("schemaVersion", (Object) 2),
                Map.of("aggregateType", (Object) "unknown"), Map.of("status", (Object) "UNKNOWN"),
                Map.of("eventType", (Object) "ingestion.succeeded"), Map.of("inputHash", (Object) "c".repeat(64)))) {
            var event = success(UUID.randomUUID());
            event.putAll(change);
            apply(event);
        }
        var unknownJob = success(UUID.randomUUID());
        unknownJob.put("jobId", UUID.randomUUID().toString());
        apply(unknownJob);
        assertEquals(2, count("SELECT count(*) FROM core.event_inbox WHERE reason='UNSUPPORTED_SCHEMA'"));
        assertEquals(3, count("SELECT count(*) FROM core.event_inbox WHERE reason='INVALID_COMPLETION'"));
        assertReceipt("UNKNOWN_JOB");
        assertEquals("QUEUED", jobStatus());
        assertEquals("QUEUED", documentStatus());
        assertEquals(0, count("SELECT count(*) FROM core.audit"));
    }

    @Test
    void staleAttemptAndFenceCannotRegressCurrentExecution() {
        admin.update("UPDATE core.job_requests SET attempt=2,last_fence=3");
        apply(event(UUID.randomUUID(), tenant, 1, 4, "RUNNING"));
        apply(event(UUID.randomUUID(), tenant, 2, 2, "RUNNING"));
        assertEquals(2, count("SELECT count(*) FROM core.event_inbox WHERE reason='OLDER_EXECUTION'"));
        assertEquals("QUEUED", jobStatus());
        assertEquals(0, count("SELECT count(*) FROM core.audit"));
    }

    @Test
    void workerProofAndMonotonicStatusAreRequiredBeforeApplyingCompletion() {
        admin.update("DELETE FROM worker.artifacts");
        admin.update("DELETE FROM worker.jobs");
        apply(success(UUID.randomUUID()));
        assertReceipt("UNPROVEN_EXECUTION");
        admin.update("INSERT INTO worker.jobs(tenant_id,job_id,case_id,kind,attempt,input_hash,status,fence,lease_owner,lease_until) "
                + "VALUES (?,?,?,'DOCUMENT',1,?,'RUNNING',2,?,now()+interval '60 seconds')", tenant, jobId, caseId, INPUT_HASH, UUID.randomUUID());
        apply(event(UUID.randomUUID(), tenant, 1, 1, "RUNNING"));
        apply(event(UUID.randomUUID(), tenant, 1, 2, "SUCCEEDED"));
        assertReceipt("MISSING_RESULT");
        apply(event(UUID.randomUUID(), tenant, 1, 2, "RUNNING"));
        assertEquals("RUNNING", jobStatus());
        assertEquals("RUNNING", documentStatus());
        apply(event(UUID.randomUUID(), tenant, 1, 2, "RUNNING"));
        apply(event(UUID.randomUUID(), tenant, 1, 2, "RETRY_WAIT"));
        assertEquals("RETRY_WAIT", jobStatus());
        assertEquals(2, count("SELECT count(*) FROM core.event_inbox WHERE reason='OLDER_STATUS'"));
        assertEquals(2, count("SELECT count(*) FROM core.audit"));
    }

    @Test
    void durableWorkerSuccessRejectsFailureBeforeApiHasReceivedSuccess() {
        apply(event(UUID.randomUUID(), tenant, 1, 1, "FAILED"));
        assertEquals(1, count("SELECT count(*) FROM core.event_inbox WHERE reason='WORKER_ALREADY_SUCCEEDED'"));
        assertEquals("QUEUED", jobStatus());
        assertEquals(0, count("SELECT count(*) FROM core.audit"));
        apply(success(UUID.randomUUID()));
        assertBusinessSuccess();
    }

    @Test
    void policyIngestionFailureUpdatesOnlyTheMatchingSource() {
        UUID source = UUID.randomUUID(), ingestion = UUID.randomUUID();
        admin.update("INSERT INTO core.sources(tenant_id,id,kind,name,media_type,upload_key,byte_size,created_by) "
                + "VALUES (?,?,'POLICY','Synthetic policy','text/plain',?,32,?)", tenant, source, "synthetic/" + source, actor);
        admin.update("INSERT INTO core.job_requests(tenant_id,job_id,source_id,kind,input,input_hash,requested_by,status) "
                + "VALUES (?,?,?,'INGESTION','{}'::jsonb,?,?,'QUEUED')", tenant, ingestion, source, INPUT_HASH, actor);
        admin.update("UPDATE core.sources SET state='INDEXING',object_key=?,sha256=?,ingestion_job_id=? WHERE id=?",
                "synthetic/policy/" + source, INPUT_HASH, ingestion, source);
        admin.update("INSERT INTO worker.jobs(tenant_id,job_id,source_id,kind,attempt,input_hash,status,fence) "
                + "VALUES (?,?,?,'INGESTION',1,?,'FAILED',1)", tenant, ingestion, source, INPUT_HASH);
        var completion = event(UUID.randomUUID(), tenant, 1, 1, "RUNNING");
        completion.put("aggregateType", "policy"); completion.put("aggregateId", source.toString());
        completion.put("jobId", ingestion.toString()); completion.put("eventType", "ingestion.running");
        apply(completion);
        assertEquals("INDEXING", db.queryForObject("SELECT state FROM core.sources WHERE id=?", String.class, source));
        completion.put("eventId", UUID.randomUUID().toString()); completion.put("status", "FAILED");
        completion.put("eventType", "ingestion.failed"); completion.put("failureCode", "SYNTHETIC_INVALID_SOURCE");
        apply(completion);
        assertEquals("FAILED", db.queryForObject("SELECT state FROM core.sources WHERE id=?", String.class, source));
        assertEquals("SYNTHETIC_INVALID_SOURCE", db.queryForObject("SELECT failure_code FROM core.sources WHERE id=?", String.class, source));
        assertEquals("QUEUED", jobStatus()); assertEquals("QUEUED", documentStatus());
        assertEquals(1, count("SELECT count(*) FROM core.audit WHERE event_type='INGESTION_FAILED' AND case_id IS NULL"));
    }

    private String jdbcUrl() {
        return "jdbc:postgresql://127.0.0.1:54320/" + databaseName;
    }

    private void apply(Map<String, Object> event) {
        tx.executeWithoutResult(status -> handler.apply(event));
    }

    private void await(CountDownLatch latch, String boundary) {
        try {
            assertTrue(latch.await(5, TimeUnit.SECONDS), "Timed out waiting for " + boundary);
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("Interrupted while waiting for " + boundary, exception);
        }
    }

    private void assertBackendWaitsOnLock(int backendPid) throws InterruptedException {
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(5);
        while (System.nanoTime() < deadline) {
            String waitType = backendWaitType(backendPid);
            if ("Lock".equals(waitType)) {
                return;
            }
            Thread.sleep(20);
        }
        assertEquals("Lock", backendWaitType(backendPid));
    }

    private String backendWaitType(int backendPid) {
        var rows = observer.queryForList(
                "SELECT wait_event_type FROM pg_stat_activity WHERE pid=?", String.class, backendPid);
        return rows.isEmpty() ? null : rows.getFirst();
    }

    private Map<String, Object> success(UUID eventId) {
        return event(eventId, tenant, 1, 1, "SUCCEEDED");
    }

    private Map<String, Object> event(UUID eventId, UUID eventTenant, int attempt, long fence, String status) {
        var event = new HashMap<String, Object>();
        event.put("eventId", eventId.toString());
        event.put("eventType", "document." + status.toLowerCase());
        event.put("schemaVersion", 1);
        event.put("tenantId", eventTenant.toString());
        event.put("aggregateId", caseId.toString());
        event.put("aggregateType", "case");
        event.put("jobId", jobId.toString());
        event.put("attempt", attempt);
        event.put("fence", fence);
        event.put("status", status);
        event.put("inputHash", INPUT_HASH);
        if ("FAILED".equals(status)) {
            event.put("failureCode", "SYNTHETIC_DELAYED_FAILURE");
        }
        return event;
    }

    private void assertBusinessSuccess() {
        assertEquals("SUCCEEDED", jobStatus());
        assertEquals("SUCCEEDED", documentStatus());
    }

    private String jobStatus() {
        return db.queryForObject("SELECT status FROM core.job_requests WHERE tenant_id=? AND job_id=?",
                String.class, tenant, jobId);
    }

    private String documentStatus() {
        return db.queryForObject("SELECT document_status FROM core.cases WHERE tenant_id=? AND id=?",
                String.class, tenant, caseId);
    }

    private int count(String sql) {
        return db.queryForObject(sql, Integer.class);
    }

    private void assertReceipt(String reason) {
        assertEquals(1, count("SELECT count(*) FROM core.event_inbox WHERE disposition='QUARANTINED' AND reason='" + reason + "'"));
    }
}
