package dev.caseflow.documents;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.DriverManager;
import java.util.Comparator;
import java.util.UUID;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.jdbc.support.JdbcTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** Actual JVM termination at transaction boundaries, using only guarded disposable SQL fixtures. */
@EnabledIfEnvironmentVariable(named = "DB_ADMIN_PASSWORD", matches = ".+")
@Timeout(90)
class CompletionProcessRecoveryTest {
    private String databaseName;
    private boolean databaseCreated;
    private JdbcTemplate db;
    private TransactionTemplate tx;
    private UUID tenant;
    private UUID caseId;
    private UUID jobId;
    private Process child;
    private Path javaArguments;
    private Thread outputReader;
    private final ArrayBlockingQueue<String> childOutput = new ArrayBlockingQueue<>(128);

    @BeforeEach
    void setup() throws Exception {
        for (String name : new String[]{"DB_ADMIN_PASSWORD", "DB_MIGRATOR_PASSWORD", "DB_API_PASSWORD"}) {
            CompletionCrashProbe.requiredEnvironment(name);
        }
        databaseName = "caseflow_test_" + UUID.randomUUID().toString().replace("-", "");
        CompletionCrashProbe.validateDatabaseName(databaseName);
        try (var connection = maintenanceConnection(); var statement = connection.createStatement()) {
            statement.setQueryTimeout(10);
            statement.execute("CREATE DATABASE " + databaseName + " OWNER caseflow_migrator");
            databaseCreated = true;
        }
        var migrator = new JdbcTemplate(new DriverManagerDataSource(CompletionCrashProbe.jdbcUrl(databaseName),
                "caseflow_migrator", CompletionCrashProbe.requiredEnvironment("DB_MIGRATOR_PASSWORD")));
        migrator.setQueryTimeout(10);
        try (var migrations = Files.list(Path.of("../../db/migrations"))) {
            for (var path : migrations.filter(p -> p.getFileName().toString().matches("V\\d+__.*\\.sql"))
                    .sorted(Comparator.comparingInt(p -> Integer.parseInt(
                            p.getFileName().toString().split("__")[0].substring(1))))
                    .toList()) {
                migrator.execute(Files.readString(path));
            }
        }
        var source = new DriverManagerDataSource(CompletionCrashProbe.jdbcUrl(databaseName),
                "caseflow_api", CompletionCrashProbe.requiredEnvironment("DB_API_PASSWORD"));
        db = new JdbcTemplate(source);
        db.setQueryTimeout(10);
        tx = new TransactionTemplate(new JdbcTransactionManager(source));
        tx.setTimeout(15);
        tenant = UUID.randomUUID();
        caseId = UUID.randomUUID();
        jobId = UUID.randomUUID();
        UUID actor = UUID.randomUUID();
        migrator.update("INSERT INTO core.identities(id,issuer,subject,display_name) VALUES (?,'https://synthetic-tests.invalid',?,'Synthetic requester')",
                actor, actor.toString());
        migrator.update("INSERT INTO core.tenants(id,name) VALUES (?,'Isolated JVM completion crash test')", tenant);
        migrator.update("INSERT INTO core.memberships(tenant_id,user_id,roles) VALUES (?,?,ARRAY['REQUESTER'])", tenant, actor);
        migrator.update("INSERT INTO core.cases(tenant_id,id,owner_id,state,purchase,approved_at,document_status,generation_id) "
                + "VALUES (?,?,?,'APPROVED','{}'::jsonb,now(),'QUEUED',?)", tenant, caseId, actor, jobId);
        migrator.update("INSERT INTO core.job_requests(tenant_id,job_id,case_id,kind,input,input_hash,requested_by,status) "
                + "VALUES (?,?,?,'DOCUMENT','{}'::jsonb,?,?,'QUEUED')", tenant, jobId, caseId, CompletionCrashProbe.INPUT_HASH, actor);
        migrator.update("INSERT INTO worker.jobs(tenant_id,job_id,case_id,kind,attempt,input_hash,status,fence) "
                + "VALUES (?,?,?,'DOCUMENT',1,?,'SUCCEEDED',1)", tenant, jobId, caseId, CompletionCrashProbe.INPUT_HASH);
        migrator.update("INSERT INTO worker.artifacts(tenant_id,job_id,attempt,fence,object_key,sha256,byte_size) "
                + "VALUES (?,?,1,1,?,?,128)", tenant, jobId, "synthetic/completion-crash/" + jobId + "/1.docx", CompletionCrashProbe.ARTIFACT_HASH);
    }

    @AfterEach
    void cleanup() throws Exception {
        try {
            if (child != null && child.isAlive()) {
                child.destroyForcibly();
                assertTrue(child.waitFor(10, TimeUnit.SECONDS), "Owned test child did not terminate during cleanup");
            }
            if (outputReader != null) {
                outputReader.join(TimeUnit.SECONDS.toMillis(2));
                assertFalse(outputReader.isAlive(), "Child output reader did not finish");
            }
        } finally {
            try {
                if (javaArguments != null) Files.deleteIfExists(javaArguments);
            } finally {
                if (databaseCreated) {
                    CompletionCrashProbe.validateDatabaseName(databaseName);
                    try (var connection = maintenanceConnection(); var statement = connection.createStatement()) {
                        statement.setQueryTimeout(10);
                        statement.execute("DROP DATABASE " + databaseName + " WITH (FORCE)");
                    }
                }
            }
        }
    }

    @Test
    void killedJvmBeforeCommitRollsBackThenReplayHasOneBusinessEffect() throws Exception {
        UUID eventId = UUID.randomUUID();
        startAtBoundary("BEFORE_COMMIT", eventId);
        assertQueuedWithoutEffects();
        forceKillOwnedChild();
        assertQueuedWithoutEffects();

        apply(eventId, "SUCCEEDED");
        apply(eventId, "SUCCEEDED");
        apply(UUID.randomUUID(), "SUCCEEDED");

        assertOneSuccess();
        assertEquals(2, count("SELECT count(*) FROM core.event_inbox"));
        assertEquals(1, count("SELECT count(*) FROM core.event_inbox WHERE disposition='STALE' AND reason='OLDER_EXECUTION'"));
    }

    @Test
    void killedJvmAfterCommitPreservesSuccessAcrossDuplicateAndLateFailure() throws Exception {
        UUID eventId = UUID.randomUUID();
        startAtBoundary("AFTER_COMMIT", eventId);
        forceKillOwnedChild();
        assertOneSuccess();
        assertEquals(1, count("SELECT count(*) FROM core.event_inbox"));

        apply(eventId, "SUCCEEDED");
        apply(UUID.randomUUID(), "SUCCEEDED");
        apply(UUID.randomUUID(), "FAILED");

        assertOneSuccess();
        assertEquals(3, count("SELECT count(*) FROM core.event_inbox"));
        assertEquals(2, count("SELECT count(*) FROM core.event_inbox WHERE disposition='STALE' AND reason='OLDER_EXECUTION'"));
        assertEquals(0, count("SELECT count(*) FROM core.audit WHERE event_type='DOCUMENT_FAILED'"));
    }

    private java.sql.Connection maintenanceConnection() throws Exception {
        CompletionCrashProbe.validateDatabaseName(databaseName);
        return DriverManager.getConnection("jdbc:postgresql://127.0.0.1:54320/postgres?connectTimeout=5&socketTimeout=10",
                "caseflow_admin", CompletionCrashProbe.requiredEnvironment("DB_ADMIN_PASSWORD"));
    }

    private void startAtBoundary(String boundary, UUID eventId) throws Exception {
        CompletionCrashProbe.validateDatabaseName(databaseName);
        String classpath = System.getProperty("caseflow.test.runtimeClasspath");
        assertNotNull(classpath, "Gradle must expose the test runtime classpath for the child JVM");
        javaArguments = Files.createTempFile("caseflow-completion-crash-", ".args");
        // A Java argument file avoids Windows command length limits; no credentials go into it.
        Files.writeString(javaArguments, "-cp\n\"" + classpath.replace("\\", "\\\\").replace("\"", "\\\"")
                + "\"\n" + CompletionCrashProbe.class.getName() + "\n" + databaseName + "\n" + boundary + "\n"
                + tenant + "\n" + caseId + "\n" + jobId + "\n" + eventId + "\n", StandardCharsets.UTF_8);
        Path java = Path.of(System.getProperty("java.home"), "bin", System.getProperty("os.name").startsWith("Windows") ? "java.exe" : "java");
        child = new ProcessBuilder(java.toString(), "@" + javaArguments).redirectErrorStream(true).start();
        outputReader = Thread.ofPlatform().daemon().start(() -> {
            try (var reader = new BufferedReader(new InputStreamReader(child.getInputStream(), StandardCharsets.UTF_8))) {
                String line;
                while ((line = reader.readLine()) != null) childOutput.offer(line);
            } catch (Exception failure) {
                childOutput.offer("OUTPUT_READER_FAILED:" + failure.getClass().getSimpleName());
            } finally {
                childOutput.offer("CHILD_OUTPUT_CLOSED");
            }
        });
        String expected = "BOUNDARY:" + boundary + ":" + eventId;
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(20);
        while (System.nanoTime() < deadline) {
            String line = childOutput.poll(Math.max(1, deadline - System.nanoTime()), TimeUnit.NANOSECONDS);
            assertNotNull(line, "Child did not reach " + boundary + " within 20 seconds");
            assertFalse(line.startsWith("PROBE_FAILED:") || line.equals("CHILD_OUTPUT_CLOSED") || line.startsWith("OUTPUT_READER_FAILED:"),
                    "Child failed before reaching " + boundary + ": " + line);
            if (expected.equals(line)) {
                assertTrue(child.isAlive(), "Child must remain blocked at the requested crash boundary");
                System.out.println("COMPLETION_CRASH_BOUNDARY boundary=" + boundary + " childPid=" + child.pid());
                return;
            }
        }
        throw new AssertionError("Child did not reach " + boundary + " within 20 seconds");
    }

    private void forceKillOwnedChild() throws Exception {
        assertTrue(child.isAlive(), "Crash evidence requires a live owned child before forced termination");
        child.destroyForcibly();
        assertTrue(child.waitFor(10, TimeUnit.SECONDS), "Owned child did not die within 10 seconds");
        assertFalse(child.isAlive());
        assertNotEquals(0, child.exitValue(), "Normal exit is not crash evidence");
        System.out.println("COMPLETION_CRASH_TERMINATED childPid=" + child.pid() + " exitCode=" + child.exitValue());
    }

    private void apply(UUID eventId, String status) {
        tx.executeWithoutResult(transaction -> CompletionCrashProbe.handler(db).apply(
                CompletionCrashProbe.event(eventId, tenant, caseId, jobId, status)));
    }

    private void assertQueuedWithoutEffects() {
        assertStatus("QUEUED");
        assertEquals(0, count("SELECT count(*) FROM core.audit"));
        assertEquals(0, count("SELECT count(*) FROM core.event_inbox"));
    }

    private void assertOneSuccess() {
        assertStatus("SUCCEEDED");
        assertEquals(1, count("SELECT count(*) FROM core.audit"));
        assertEquals(1, count("SELECT count(*) FROM core.audit WHERE event_type='DOCUMENT_SUCCEEDED'"));
        assertEquals(1, count("SELECT count(*) FROM core.event_inbox WHERE disposition='APPLIED'"));
    }

    private void assertStatus(String expected) {
        assertEquals(expected, db.queryForObject("SELECT status FROM core.job_requests WHERE tenant_id=? AND job_id=?", String.class, tenant, jobId));
        assertEquals(expected, db.queryForObject("SELECT document_status FROM core.cases WHERE tenant_id=? AND id=?", String.class, tenant, caseId));
    }

    private int count(String sql) {
        return db.queryForObject(sql, Integer.class);
    }
}
