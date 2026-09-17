package dev.caseflow.documents;

import dev.caseflow.common.Json;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.sql.DriverManager;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.*;
import org.apache.kafka.clients.admin.*;
import org.apache.kafka.clients.consumer.*;
import org.apache.kafka.clients.producer.*;
import org.apache.kafka.common.TopicPartition;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import tools.jackson.databind.json.JsonMapper;

import static org.junit.jupiter.api.Assertions.*;

/** Real broker/SQL proof; changing publication persistence or committing offsets early must fail. */
@EnabledIfEnvironmentVariable(named = "CASEFLOW_KAFKA_PROCESS_TESTS", matches = "1")
@Timeout(150)
class KafkaMessagingProcessRecoveryTest {
    private static final Json JSON = new Json(JsonMapper.builder().build());
    private String databaseName;
    private String namespace;
    private boolean databaseCreated;
    private JdbcTemplate db;
    private UUID tenant, caseId, jobId;
    private Admin admin;
    private final List<OwnedChild> children = new ArrayList<>();

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
        tenant = UUID.randomUUID();
        caseId = UUID.randomUUID();
        jobId = UUID.randomUUID();
        namespace = "caseflow_test_" + UUID.randomUUID().toString().replace("-", "");
        KafkaMessagingCrashProbe.validateNamespace(namespace);
        admin = Admin.create(Map.of("bootstrap.servers", KafkaMessagingCrashProbe.BROKERS,
                "request.timeout.ms", 10000, "default.api.timeout.ms", 15000));
        admin.createTopics(topics().stream().map(name -> new NewTopic(name, 1, (short) 1)).toList()).all().get(15, TimeUnit.SECONDS);
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
        var failures = new ArrayList<Throwable>();
        for (var child : children) attemptCleanup(failures, child::close);
        if (admin != null) {
            Admin ownedAdmin = admin;
            try {
                KafkaMessagingCrashProbe.validateNamespace(namespace);
                for (String group : List.of(namespace + ".consumer", namespace + ".observer")) {
                    attemptCleanup(failures, () -> deleteOwnedGroup(ownedAdmin, group));
                }
            } finally {
                // Topic cleanup is independent of group deletion, including a broker-side failure.
                attemptCleanup(failures, () -> ownedAdmin.deleteTopics(topics()).all().get(15, TimeUnit.SECONDS));
                attemptCleanup(failures, () -> ownedAdmin.close(Duration.ofSeconds(5)));
                admin = null;
            }
        }
        if (databaseCreated) {
            attemptCleanup(failures, () -> {
                CompletionCrashProbe.validateDatabaseName(databaseName);
                try (var connection = maintenanceConnection(); var statement = connection.createStatement()) {
                    statement.setQueryTimeout(10);
                    statement.execute("DROP DATABASE " + databaseName + " WITH (FORCE)");
                    databaseCreated = false;
                }
            });
        }
        if (!failures.isEmpty()) {
            Throwable first = failures.getFirst();
            failures.stream().skip(1).forEach(first::addSuppressed);
            if (first instanceof Exception exception) throw exception;
            throw (AssertionError) first;
        }
    }

    private static void deleteOwnedGroup(Admin ownedAdmin, String group) throws Exception {
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(15);
        boolean waiting = false;
        while (true) {
            try {
                ownedAdmin.deleteConsumerGroups(List.of(group)).all()
                        .get(Math.max(1, deadline - System.nanoTime()), TimeUnit.NANOSECONDS);
                return;
            } catch (ExecutionException failure) {
                if (failure.getCause() instanceof org.apache.kafka.common.errors.GroupIdNotFoundException) return;
                if (!(failure.getCause() instanceof org.apache.kafka.common.errors.GroupNotEmptyException)
                        || System.nanoTime() >= deadline) throw failure;
                if (!waiting) System.out.println("KAFKA_CLEANUP_WAIT group=" + group + " reason=live-membership-after-kill");
                waiting = true;
                Thread.sleep(200);
            }
        }
    }

    @FunctionalInterface private interface CleanupAction { void run() throws Exception; }
    private static void attemptCleanup(List<Throwable> failures, CleanupAction action) {
        try { action.run(); }
        catch (Exception | AssertionError failure) { failures.add(failure); }
    }
    @Test
    void cleanupAfterAbruptConsumerDeathRemovesOwnedGroupAndTopics() throws Exception {
        sendCompletion();
        var child = start("COMPLETE", "NONE");
        child.boundary("COMPLETION_BEFORE_OFFSET");
        child.kill();
        cleanup();
        try (var verifier = Admin.create(Map.of("bootstrap.servers", KafkaMessagingCrashProbe.BROKERS,
                "request.timeout.ms", 10000, "default.api.timeout.ms", 15000))) {
            assertTrue(Collections.disjoint(topics(), verifier.listTopics().names().get(15, TimeUnit.SECONDS)));
            assertTrue(verifier.listConsumerGroups().all().get(15, TimeUnit.SECONDS).stream()
                    .noneMatch(group -> group.groupId().equals(namespace + ".consumer")));
        }
        System.out.println("KAFKA_CLEANUP_VERIFIED namespace=" + namespace + " liveMembershipKill=true");
    }

    @Test
    void publisherKilledAfterActualAckRepublishesSameEventAtNewOffset() throws Exception {
        UUID event = seedOutbox();
        var first = start("PUBLISH", "NONE");
        Map<String, Object> firstBoundary = first.boundary("PUBLISH_ACK");
        assertEquals(event.toString(), firstBoundary.get("eventId"));
        assertEquals(0, published());
        first.kill();
        assertEquals(0, published());
        var restarted = start("PUBLISH", "NONE");
        Map<String, Object> nextBoundary = restarted.boundary("PUBLISH_ACK");
        assertEquals(firstBoundary.get("eventId"), nextBoundary.get("eventId"));
        assertEquals(firstBoundary.get("topic"), nextBoundary.get("topic"));
        assertEquals(firstBoundary.get("partition"), nextBoundary.get("partition"));
        assertEquals(number(firstBoundary, "offset") + 1, number(nextBoundary, "offset"));
        restarted.release();
        assertEquals(1, published(), "Recovery must persist broker acknowledgement to the outbox");
        assertBrokerEvents(event, 2);
    }

    @Test
    void publisherNormalReleasePersistsAckWithoutDuplicate() throws Exception {
        UUID event = seedOutbox();
        var child = start("PUBLISH", "NONE");
        child.boundary("PUBLISH_ACK");
        assertEquals(0, published());
        child.release();
        assertEquals(1, published());
        assertBrokerEvents(event, 1);
    }

    @Test
    void completionKilledAfterSqlCommitReplaysSameBrokerOffsetWithoutDoubleAudit() throws Exception {
        UUID event = sendCompletion();
        var first = start("COMPLETE", "NONE");
        Map<String, Object> firstBoundary = first.boundary("COMPLETION_BEFORE_OFFSET");
        assertOneSuccess();
        assertOffsetAbsent();
        first.kill();
        assertOneSuccess();
        assertOffsetAbsent();
        var restarted = start("COMPLETE", "NONE");
        Map<String, Object> nextBoundary = restarted.boundary("COMPLETION_BEFORE_OFFSET");
        assertEquals(firstBoundary, nextBoundary, "Restart must redeliver the same broker coordinate");
        assertEquals(event.toString(), first.delivered.getFirst().get("eventId"));
        assertEquals(first.delivered, restarted.delivered);
        restarted.release();
        assertOneSuccess();
        assertEquals(1L, committedOffset());
        System.out.println("KAFKA_RECOVERY_REPLAY " + JSON.write(Map.of("eventId", event, "coordinate", nextBoundary,
                "committedOffset", committedOffset(), "auditCount", count("SELECT count(*) FROM core.audit"))));
    }

    @Test
    void completionNormalReleaseCommitsOffsetAfterOneBusinessEffect() throws Exception {
        sendCompletion();
        var child = start("COMPLETE", "NONE");
        child.boundary("COMPLETION_BEFORE_OFFSET");
        assertOneSuccess();
        assertOffsetAbsent();
        child.release();
        assertOneSuccess();
        assertEquals(1L, committedOffset());
    }

    @Test
    void detectorRejectsEarlyOffsetCommit() throws Exception {
        sendCompletion();
        var child = start("COMPLETE", "EARLY_OFFSET");
        child.boundary("COMPLETION_BEFORE_OFFSET");
        assertOneSuccess();
        assertThrows(AssertionError.class, this::assertOffsetAbsent);
        assertEquals(1L, committedOffset());
        child.release();
        System.out.println("KAFKA_CONTROL_REJECTED fault=EARLY_OFFSET");
    }

    @Test
    void detectorRejectsOffsetBoundaryWithoutPersistedCompletion() throws Exception {
        sendCompletion();
        var child = start("COMPLETE", "MISSING_PERSISTENCE");
        child.boundary("COMPLETION_BEFORE_OFFSET");
        assertThrows(AssertionError.class, this::assertOneSuccess);
        assertEquals("QUEUED", db.queryForObject("SELECT status FROM core.job_requests", String.class));
        assertEquals(0, count("SELECT count(*) FROM core.audit"));
        assertOffsetAbsent();
        child.release();
        System.out.println("KAFKA_CONTROL_REJECTED fault=MISSING_PERSISTENCE");
    }

    private List<String> topics() { return List.of(namespace + ".jobs", namespace + ".completions", namespace + ".deadletters"); }
    private java.sql.Connection maintenanceConnection() throws Exception {
        CompletionCrashProbe.validateDatabaseName(databaseName);
        return DriverManager.getConnection("jdbc:postgresql://127.0.0.1:54320/postgres?connectTimeout=5&socketTimeout=10",
                "caseflow_admin", CompletionCrashProbe.requiredEnvironment("DB_ADMIN_PASSWORD"));
    }

    private UUID seedOutbox() {
        UUID event = UUID.randomUUID();
        var payload = Map.of("eventId", event, "aggregateId", caseId, "tenantId", tenant,
                "eventType", "document.requested", "schemaVersion", 1, "jobId", jobId);
        db.update("INSERT INTO core.outbox(event_id,tenant_id,case_id,event_type,payload) VALUES (?,?,?,'document.requested',?::jsonb)",
                event, tenant, caseId, JSON.write(payload));
        return event;
    }

    private UUID sendCompletion() throws Exception {
        UUID event = UUID.randomUUID();
        try (var producer = new KafkaProducer<String, String>(KafkaMessagingCrashProbe.producerProperties())) {
            var result = producer.send(new ProducerRecord<>(namespace + ".completions", tenant + ":" + caseId,
                    JSON.write(CompletionCrashProbe.event(event, tenant, caseId, jobId, "SUCCEEDED")))).get(20, TimeUnit.SECONDS);
            assertEquals(0L, result.offset());
        }
        return event;
    }

    private void assertBrokerEvents(UUID event, int expected) {
        try (var observer = new KafkaConsumer<String, String>(KafkaMessagingCrashProbe.consumerProperties(namespace + ".observer"))) {
            var partition = new TopicPartition(namespace + ".jobs", 0);
            observer.assign(List.of(partition));
            observer.seekToBeginning(List.of(partition));
            assertEquals((long) expected, observer.endOffsets(List.of(partition)).get(partition));
            var records = new ArrayList<ConsumerRecord<String, String>>();
            long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(15);
            while (records.size() < expected && System.nanoTime() < deadline) {
                observer.poll(Duration.ofMillis(500)).forEach(records::add);
            }
            assertEquals(expected, records.size());
            for (int i = 0; i < expected; i++) {
                assertEquals(event.toString(), JSON.object(records.get(i).value()).get("eventId"));
                assertEquals((long) i, records.get(i).offset());
                assertEquals(tenant + ":" + caseId, records.get(i).key());
            }
            System.out.println("KAFKA_PUBLISH_VERIFIED " + JSON.write(Map.of("eventId", event, "topic", partition.topic(),
                    "partition", 0, "offsets", records.stream().map(ConsumerRecord::offset).toList(), "publishedRows", published())));
        }
    }

    private Long committedOffset() throws Exception {
        var offsets = admin.listConsumerGroupOffsets(namespace + ".consumer").partitionsToOffsetAndMetadata().get(10, TimeUnit.SECONDS);
        var committed = offsets.get(new TopicPartition(namespace + ".completions", 0));
        return committed == null ? null : committed.offset();
    }
    private void assertOffsetAbsent() throws Exception { assertNull(committedOffset(), "Offset must remain uncommitted at SQL boundary"); }
    private int published() { return count("SELECT count(*) FROM core.outbox WHERE published_at IS NOT NULL"); }
    private int count(String sql) { return db.queryForObject(sql, Integer.class); }
    private void assertOneSuccess() {
        assertEquals("SUCCEEDED", db.queryForObject("SELECT status FROM core.job_requests", String.class));
        assertEquals("SUCCEEDED", db.queryForObject("SELECT document_status FROM core.cases", String.class));
        assertEquals(1, count("SELECT count(*) FROM core.audit"));
        assertEquals(1, count("SELECT count(*) FROM core.audit WHERE event_type='DOCUMENT_SUCCEEDED'"));
        assertEquals(1, count("SELECT count(*) FROM core.event_inbox"));
        assertEquals(1, count("SELECT count(*) FROM core.event_inbox WHERE disposition='APPLIED'"));
    }
    private static long number(Map<String, Object> data, String key) { return ((Number) data.get(key)).longValue(); }

    private OwnedChild start(String mode, String fault) throws Exception {
        var child = new OwnedChild(mode, fault);
        children.add(child);
        return child;
    }

    private final class OwnedChild implements AutoCloseable {
        final Process process;
        final Path arguments;
        final Thread reader;
        final BlockingQueue<String> output = new LinkedBlockingQueue<>(128);
        final List<Map<String, Object>> delivered = new ArrayList<>();

        OwnedChild(String mode, String fault) throws Exception {
            String classpath = java.nio.file.Files.readString(java.nio.file.Path.of(System.getProperty("caseflow.test.runtimeClasspathFile")));
            assertNotNull(classpath);
            arguments = Files.createTempFile("caseflow-kafka-crash-", ".args");
            Files.writeString(arguments, "-cp\n\"" + classpath.replace("\\", "\\\\").replace("\"", "\\\"")
                    + "\"\n" + KafkaMessagingCrashProbe.class.getName() + "\n" + databaseName + "\n" + namespace
                    + "\n" + mode + "\n" + fault + "\n", StandardCharsets.UTF_8);
            Path java = Path.of(System.getProperty("java.home"), "bin", System.getProperty("os.name").startsWith("Windows") ? "java.exe" : "java");
            process = new ProcessBuilder(java.toString(), "@" + arguments).redirectErrorStream(true).start();
            reader = Thread.ofPlatform().daemon().start(() -> {
                try (var lines = new BufferedReader(new InputStreamReader(process.getInputStream(), StandardCharsets.UTF_8))) {
                    String line;
                    while ((line = lines.readLine()) != null) {
                        if (line.startsWith("BOUNDARY:") || line.startsWith("DELIVERED:") || line.startsWith("PROBE_")) output.put(line);
                    }
                } catch (Exception failure) { output.offer("PROBE_FAILED:OUTPUT_READER"); }
                finally { output.offer("CHILD_CLOSED"); }
            });
        }

        Map<String, Object> boundary(String expected) throws Exception {
            long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(40);
            while (System.nanoTime() < deadline) {
                String line = output.poll(Math.max(1, deadline - System.nanoTime()), TimeUnit.NANOSECONDS);
                assertNotNull(line, "Child boundary timeout: " + expected);
                assertFalse(line.startsWith("PROBE_FAILED") || line.equals("CHILD_CLOSED"), "Child failed before boundary: " + line);
                if (line.startsWith("DELIVERED:")) delivered.add(JSON.object(line.substring("DELIVERED:".length())));
                if (line.startsWith("BOUNDARY:" + expected + ":")) {
                    assertTrue(process.isAlive(), "Boundary must have a live owned child");
                    System.out.println("KAFKA_CRASH_BOUNDARY pid=" + process.pid() + " database=" + databaseName + " " + line);
                    return JSON.object(line.substring(("BOUNDARY:" + expected + ":").length()));
                }
            }
            throw new AssertionError("Expected child boundary " + expected);
        }

        void kill() throws Exception {
            assertTrue(process.isAlive());
            process.destroyForcibly();
            assertTrue(process.waitFor(10, TimeUnit.SECONDS));
            assertNotEquals(0, process.exitValue(), "Normal exit cannot establish a crash");
            System.out.println("KAFKA_CRASH_KILLED pid=" + process.pid() + " exit=" + process.exitValue());
        }

        void release() throws Exception {
            assertTrue(process.isAlive());
            process.getOutputStream().write("RELEASE\n".getBytes(StandardCharsets.UTF_8));
            process.getOutputStream().flush();
            assertTrue(process.waitFor(20, TimeUnit.SECONDS), "Released child must finish normally");
            assertEquals(0, process.exitValue());
            System.out.println("KAFKA_CONTROL_RELEASE pid=" + process.pid() + " exit=" + process.exitValue());
        }

        @Override public void close() throws Exception {
            try {
                if (process.isAlive()) { process.destroyForcibly(); assertTrue(process.waitFor(10, TimeUnit.SECONDS)); }
                reader.join(2000);
                assertFalse(reader.isAlive());
            } finally { Files.deleteIfExists(arguments); }
        }
    }
}
