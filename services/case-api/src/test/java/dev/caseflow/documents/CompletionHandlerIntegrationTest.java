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
            var start = new CountDownLatch(1);
            try (var executor = Executors.newFixedThreadPool(2)) {
                UUID eventId = UUID.randomUUID();
                var first = executor.submit(() -> applyAfter(start, success(eventId)));
                var second = executor.submit(() -> applyAfter(start, success(eventId)));
                start.countDown();
                first.get(8, TimeUnit.SECONDS);
                second.get(8, TimeUnit.SECONDS);
            }
        });

        assertBusinessSuccess();
        assertEquals(1, count("SELECT count(*) FROM core.event_inbox WHERE disposition='APPLIED'"));
        assertEquals(1, count("SELECT count(*) FROM core.audit WHERE event_type='DOCUMENT_SUCCEEDED'"));
    }

    private String jdbcUrl() {
        return "jdbc:postgresql://127.0.0.1:54320/" + databaseName;
    }

    private void apply(Map<String, Object> event) {
        tx.executeWithoutResult(status -> handler.apply(event));
    }

    private void applyAfter(CountDownLatch start, Map<String, Object> event) {
        try {
            assertTrue(start.await(2, TimeUnit.SECONDS));
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("Interrupted before concurrent completion", exception);
        }
        apply(event);
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
