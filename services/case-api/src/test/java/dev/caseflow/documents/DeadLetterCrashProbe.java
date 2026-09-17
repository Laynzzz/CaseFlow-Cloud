package dev.caseflow.documents;

import dev.caseflow.common.Json;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Proxy;
import java.util.*;
import java.util.concurrent.*;
import org.apache.kafka.clients.consumer.*;
import org.apache.kafka.clients.producer.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.jdbc.support.JdbcTransactionManager;
import tools.jackson.databind.json.JsonMapper;

/** Test-only child: production poison handling with real loopback Kafka and disposable SQL. */
public final class DeadLetterCrashProbe {
    private static final Json JSON = new Json(JsonMapper.builder().build());

    public static void main(String[] args) {
        try {
            if (args.length != 3) throw new IllegalArgumentException("Expected database, namespace, boundary");
            String database = args[0], namespace = args[1], boundary = args[2];
            KafkaMessagingCrashProbe.validateNamespace(namespace);
            if (!Set.of("BEFORE_SEND", "AFTER_ACK", "RECOVER").contains(boundary)) {
                throw new IllegalArgumentException("Unknown dead-letter boundary");
            }
            var source = new DriverManagerDataSource(CompletionCrashProbe.jdbcUrl(database),
                    "caseflow_api", CompletionCrashProbe.requiredEnvironment("DB_API_PASSWORD"));
            var db = new JdbcTemplate(source);
            db.setQueryTimeout(10);
            var completed = new CountDownLatch(1);
            var acknowledged = new java.util.concurrent.atomic.AtomicBoolean();
            var realProducer = new KafkaProducer<String, String>(KafkaMessagingCrashProbe.producerProperties());
            Producer<String, String> producer = intercept(Producer.class, realProducer, (method, parameters) -> {
                if (method.getName().equals("send") && parameters.length == 1) {
                    var record = (ProducerRecord<?, ?>) parameters[0];
                    if (!record.topic().equals(namespace + ".deadletters")) throw new IllegalStateException("Unexpected destination");
                    if (boundary.equals("BEFORE_SEND")) checkpoint(boundary, Map.of("acknowledged", false));
                    @SuppressWarnings("unchecked") var future = (Future<RecordMetadata>) invoke(method, realProducer, parameters);
                    return new Future<RecordMetadata>() {
                        public boolean cancel(boolean interrupt) { return future.cancel(interrupt); }
                        public boolean isCancelled() { return future.isCancelled(); }
                        public boolean isDone() { return future.isDone(); }
                        public RecordMetadata get() throws InterruptedException, ExecutionException { return reached(future.get()); }
                        public RecordMetadata get(long timeout, TimeUnit unit) throws InterruptedException, ExecutionException, TimeoutException {
                            return reached(future.get(timeout, unit));
                        }
                        private RecordMetadata reached(RecordMetadata metadata) {
                            acknowledged.set(true);
                            if (boundary.equals("AFTER_ACK")) checkpoint(boundary, Map.of("acknowledged", true,
                                    "topic", metadata.topic(), "partition", metadata.partition(), "offset", metadata.offset()));
                            return metadata;
                        }
                    };
                }
                return invoke(method, realProducer, parameters);
            });
            var realConsumer = new KafkaConsumer<String, String>(KafkaMessagingCrashProbe.consumerProperties(namespace + ".consumer"));
            Consumer<String, String> consumer = intercept(Consumer.class, realConsumer, (method, parameters) -> {
                if (method.getName().equals("commitSync")) {
                    if (!acknowledged.get()) throw new AssertionError("Source offset committed before dead-letter acknowledgement");
                    Object result = invoke(method, realConsumer, parameters);
                    completed.countDown();
                    return result;
                }
                Object result = invoke(method, realConsumer, parameters);
                if (method.getName().equals("poll") && result instanceof ConsumerRecords<?, ?> records) {
                    for (var record : records) {
                        System.out.println("DELIVERED:" + JSON.write(Map.of("topic", record.topic(),
                                "partition", record.partition(), "offset", record.offset())));
                    }
                }
                return result;
            });
            var messaging = new JobMessaging(db, JSON, CompletionCrashProbe.handler(db), new JdbcTransactionManager(source),
                    producer, consumer, namespace + ".jobs", namespace + ".completions", namespace + ".deadletters");
            messaging.start();
            if (!completed.await(65, TimeUnit.SECONDS)) throw new IllegalStateException("Recovery deadline elapsed");
            messaging.stop();
            System.out.println("PROBE_COMPLETED");
        } catch (Throwable failure) {
            System.err.println("PROBE_FAILED:" + failure.getClass().getSimpleName());
            System.exit(2);
        }
    }

    private static void checkpoint(String boundary, Map<String, Object> metadata) {
        var release = new CompletableFuture<String>();
        Thread.ofPlatform().daemon().start(() -> {
            try { release.complete(new BufferedReader(new InputStreamReader(System.in)).readLine()); }
            catch (Exception failure) { release.completeExceptionally(failure); }
        });
        System.out.println("BOUNDARY:" + boundary + ":" + JSON.write(metadata));
        System.out.flush();
        try {
            if (!"RELEASE".equals(release.get(45, TimeUnit.SECONDS))) throw new IllegalStateException("Invalid parent command");
        } catch (Exception failure) { throw new IllegalStateException("Parent release deadline", failure); }
    }

    @FunctionalInterface private interface Invocation { Object call(java.lang.reflect.Method method, Object[] args) throws Throwable; }
    @SuppressWarnings("unchecked")
    private static <T> T intercept(Class<?> type, T delegate, Invocation invocation) {
        return (T) Proxy.newProxyInstance(delegate.getClass().getClassLoader(), new Class<?>[]{type},
                (ignored, method, args) -> invocation.call(method, args == null ? new Object[0] : args));
    }
    private static Object invoke(java.lang.reflect.Method method, Object target, Object[] args) throws Throwable {
        try { return method.invoke(target, args); }
        catch (InvocationTargetException failure) { throw failure.getCause(); }
    }
}
