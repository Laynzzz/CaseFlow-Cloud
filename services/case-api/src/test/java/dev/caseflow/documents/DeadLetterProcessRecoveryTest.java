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

/** Real poison handling: two distinct forced-kill boundaries, each followed by a fresh child. */
@EnabledIfEnvironmentVariable(named = "CASEFLOW_KAFKA_PROCESS_TESTS", matches = "1")
@Timeout(150)
class DeadLetterProcessRecoveryTest {
    private static final Json JSON = new Json(JsonMapper.builder().build());
    private String databaseName;
    private String namespace;
    private boolean databaseCreated;
    private JdbcTemplate db;
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
        namespace = "caseflow_test_" + UUID.randomUUID().toString().replace("-", "");
        KafkaMessagingCrashProbe.validateNamespace(namespace);
        admin = Admin.create(Map.of("bootstrap.servers", KafkaMessagingCrashProbe.BROKERS,
                "request.timeout.ms", 10000, "default.api.timeout.ms", 15000));
        admin.createTopics(topics().stream().map(name -> new NewTopic(name, 1, (short) 1)).toList()).all().get(15, TimeUnit.SECONDS);
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
    @org.junit.jupiter.params.ParameterizedTest
    @org.junit.jupiter.params.provider.ValueSource(strings = {"BEFORE_SEND", "AFTER_ACK"})
    void poisonRecordSurvivesDeathBeforeSourceOffsetCommit(String boundary) throws Exception {
        String sentinel = "synthetic-private-poison-" + UUID.randomUUID();
        String poison = JSON.write(Map.of("privateContent", sentinel));
        var coordinate = Map.<String, Object>of("topic", namespace + ".completions", "partition", 0, "offset", 0);
        try (var producer = new KafkaProducer<String, String>(KafkaMessagingCrashProbe.producerProperties())) {
            assertEquals(0L, producer.send(new ProducerRecord<>(namespace + ".completions", "synthetic-invalid", poison))
                    .get(20, TimeUnit.SECONDS).offset());
        }
        var first = start(boundary);
        var reached = first.boundary(boundary);
        assertEquals(boundary.equals("AFTER_ACK"), reached.get("acknowledged"));
        assertEquals(List.of(coordinate), first.delivered);
        assertNull(committedOffset(), "Source offset must remain absent until dead-letter acknowledgement");
        int initial = boundary.equals("AFTER_ACK") ? 1 : 0;
        assertDeadletters(initial, coordinate, poison, sentinel);
        first.kill();
        assertNull(committedOffset());
        assertNoBusinessEffects();
        var recovered = start("RECOVER");
        recovered.finish();
        assertEquals(first.delivered, recovered.delivered, "Recovery must replay the same source coordinate");
        assertEquals(1L, committedOffset());
        assertDeadletters(initial + 1, coordinate, poison, sentinel);
        assertNoBusinessEffects();
        System.out.println("DEADLETTER_RECOVERY_VERIFIED " + JSON.write(Map.of("boundary", boundary,
                "source", coordinate, "deadletterCount", initial + 1, "committedOffset", committedOffset(),
                "redactionVerified", true, "businessEffects", 0)));
    }

    private Long committedOffset() throws Exception {
        var offsets = admin.listConsumerGroupOffsets(namespace + ".consumer").partitionsToOffsetAndMetadata().get(10, TimeUnit.SECONDS);
        var committed = offsets.get(new TopicPartition(namespace + ".completions", 0));
        return committed == null ? null : committed.offset();
    }

    private void assertNoBusinessEffects() {
        for (String table : List.of("core.event_inbox", "core.audit", "core.outbox", "core.job_requests")) {
            assertEquals(0, db.queryForObject("SELECT count(*) FROM " + table, Integer.class));
        }
    }

    private void assertDeadletters(int expected, Map<String, Object> sourceCoordinate, String poison, String sentinel) {
        try (var observer = new KafkaConsumer<String, String>(KafkaMessagingCrashProbe.consumerProperties(namespace + ".observer"))) {
            var partition = new TopicPartition(namespace + ".deadletters", 0);
            observer.assign(List.of(partition));
            observer.seekToBeginning(List.of(partition));
            assertEquals((long) expected, observer.endOffsets(List.of(partition)).get(partition));
            var records = new ArrayList<ConsumerRecord<String, String>>();
            long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(15);
            while (records.size() < expected && System.nanoTime() < deadline) observer.poll(Duration.ofMillis(500)).forEach(records::add);
            assertEquals(expected, records.size());
            for (int i = 0; i < expected; i++) {
                var record = records.get(i);
                assertFalse(record.value().contains(sentinel), "Raw poison content reached dead-letter topic");
                assertEquals("invalid-completion", record.key());
                assertEquals((long) i, record.offset());
                var payload = JSON.object(record.value());
                assertEquals(Set.of("reason", "topic", "partition", "offset", "hash"), payload.keySet());
                assertEquals("INVALID_COMPLETION_ENVELOPE", payload.get("reason"));
                assertEquals(JSON.hash(poison), payload.get("hash"));
                for (String field : List.of("topic", "partition", "offset")) assertEquals(sourceCoordinate.get(field), payload.get(field));
            }
        }
    }

    private List<String> topics() { return List.of(namespace + ".jobs", namespace + ".completions", namespace + ".deadletters"); }
    private java.sql.Connection maintenanceConnection() throws Exception {
        CompletionCrashProbe.validateDatabaseName(databaseName);
        return DriverManager.getConnection("jdbc:postgresql://127.0.0.1:54320/postgres?connectTimeout=5&socketTimeout=10",
                "caseflow_admin", CompletionCrashProbe.requiredEnvironment("DB_ADMIN_PASSWORD"));
    }

    private OwnedChild start(String mode) throws Exception {
        var child = new OwnedChild(mode);
        children.add(child);
        return child;
    }

    private final class OwnedChild implements AutoCloseable {
        final Process process;
        final Path arguments;
        final Thread reader;
        final BlockingQueue<String> output = new LinkedBlockingQueue<>(128);
        final List<Map<String, Object>> delivered = new ArrayList<>();

        OwnedChild(String mode) throws Exception {
            String classpath = java.nio.file.Files.readString(java.nio.file.Path.of(System.getProperty("caseflow.test.runtimeClasspathFile")));
            assertNotNull(classpath);
            arguments = Files.createTempFile("caseflow-kafka-crash-", ".args");
            Files.writeString(arguments, "-cp\n\"" + classpath.replace("\\", "\\\\").replace("\"", "\\\"")
                    + "\"\n" + DeadLetterCrashProbe.class.getName() + "\n" + databaseName + "\n" + namespace
                    + "\n" + mode + "\n", StandardCharsets.UTF_8);
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

        void finish() throws Exception {
            assertTrue(process.waitFor(35, TimeUnit.SECONDS), "Recovery child deadline");
            reader.join(2000);
            assertEquals(0, process.exitValue(), "Recovery child must finish normally");
            boolean completed = false;
            for (String line : output) {
                assertFalse(line.startsWith("PROBE_FAILED"), "Recovery failed");
                if (line.startsWith("DELIVERED:")) delivered.add(JSON.object(line.substring("DELIVERED:".length())));
                completed |= line.equals("PROBE_COMPLETED");
            }
            assertTrue(completed);
            System.out.println("DEADLETTER_RECOVERED pid=" + process.pid() + " exit=" + process.exitValue());
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
