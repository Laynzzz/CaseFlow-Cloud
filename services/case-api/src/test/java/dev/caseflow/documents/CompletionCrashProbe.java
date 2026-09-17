package dev.caseflow.documents;

import dev.caseflow.common.Commands;
import dev.caseflow.common.Json;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.jdbc.support.JdbcTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import tools.jackson.databind.json.JsonMapper;

/** Child JVM fixture only: real production handler, no API server, broker, or provider. */
public final class CompletionCrashProbe {
    static final String INPUT_HASH = "a".repeat(64);
    static final String ARTIFACT_HASH = "b".repeat(64);

    private CompletionCrashProbe() {}

    public static void main(String[] args) {
        try {
            if (args.length != 6) throw new IllegalArgumentException("Expected disposable database and fixture IDs");
            String databaseName = args[0];
            String boundary = args[1];
            if (!boundary.equals("BEFORE_COMMIT") && !boundary.equals("AFTER_COMMIT")) {
                throw new IllegalArgumentException("Unknown crash boundary");
            }
            UUID tenant = UUID.fromString(args[2]);
            UUID caseId = UUID.fromString(args[3]);
            UUID jobId = UUID.fromString(args[4]);
            UUID eventId = UUID.fromString(args[5]);
            var source = new DriverManagerDataSource(jdbcUrl(databaseName),
                    "caseflow_api", requiredEnvironment("DB_API_PASSWORD"));
            var db = new JdbcTemplate(source);
            var tx = new TransactionTemplate(new JdbcTransactionManager(source));
            tx.setTimeout(60);
            var handler = handler(db);
            tx.executeWithoutResult(status -> {
                if (!"caseflow_api".equals(db.queryForObject("SELECT current_user", String.class))) {
                    throw new IllegalStateException("Probe must execute as the API role");
                }
                handler.apply(event(eventId, tenant, caseId, jobId, "SUCCEEDED"));
                if (!"SUCCEEDED".equals(db.queryForObject(
                        "SELECT status FROM core.job_requests WHERE tenant_id=? AND job_id=?",
                        String.class, tenant, jobId))
                        || db.queryForObject("SELECT count(*) FROM core.audit", Integer.class) != 1
                        || db.queryForObject("SELECT count(*) FROM core.event_inbox WHERE disposition='APPLIED'", Integer.class) != 1) {
                    throw new IllegalStateException("Completion business effects were not applied inside transaction");
                }
                if (boundary.equals("BEFORE_COMMIT")) reachedBoundary(boundary, eventId);
            });
            if (boundary.equals("AFTER_COMMIT")) reachedBoundary(boundary, eventId);
        } catch (Exception failure) {
            // Avoid printing connection configuration or inherited credentials on failure.
            System.err.println("PROBE_FAILED:" + failure.getClass().getSimpleName());
            System.exit(2);
        }
    }

    private static void reachedBoundary(String boundary, UUID eventId) {
        var release = new CompletableFuture<String>();
        Thread.ofPlatform().daemon().start(() -> {
            try {
                release.complete(new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8)).readLine());
            } catch (Exception failure) {
                release.completeExceptionally(failure);
            }
        });
        System.out.println("BOUNDARY:" + boundary + ":" + eventId);
        System.out.flush();
        try {
            if (!"RELEASE".equals(release.get(45, TimeUnit.SECONDS))) {
                throw new IllegalStateException("Unexpected parent command");
            }
        } catch (Exception failure) {
            throw new IllegalStateException("Parent did not release or terminate child within deadline", failure);
        }
    }

    static void validateDatabaseName(String name) {
        if (name == null || !name.matches("caseflow_test_[a-f0-9]{32}")) {
            throw new IllegalArgumentException("Refusing non-disposable completion test database");
        }
    }

    static String jdbcUrl(String databaseName) {
        validateDatabaseName(databaseName);
        return "jdbc:postgresql://127.0.0.1:54320/" + databaseName + "?connectTimeout=5&socketTimeout=10";
    }

    static String requiredEnvironment(String name) {
        String value = System.getenv(name);
        if (value == null || value.isBlank()) throw new IllegalStateException("Missing required environment variable " + name);
        return value;
    }

    static CompletionHandler handler(JdbcTemplate db) {
        return new CompletionHandler(db, new Commands(db, new Json(JsonMapper.builder().build())));
    }

    static Map<String, Object> event(UUID eventId, UUID tenant, UUID caseId, UUID jobId, String status) {
        var event = new HashMap<String, Object>();
        event.put("eventId", eventId.toString());
        event.put("eventType", "document." + status.toLowerCase(java.util.Locale.ROOT));
        event.put("schemaVersion", 1);
        event.put("tenantId", tenant.toString());
        event.put("aggregateId", caseId.toString());
        event.put("aggregateType", "case");
        event.put("jobId", jobId.toString());
        event.put("attempt", 1);
        event.put("fence", 1L);
        event.put("status", status);
        event.put("inputHash", INPUT_HASH);
        if (status.equals("FAILED")) event.put("failureCode", "SYNTHETIC_DELAYED_FAILURE");
        return event;
    }
}
