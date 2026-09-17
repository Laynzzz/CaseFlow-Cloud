package dev.caseflow.documents;

import dev.caseflow.common.Json;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Proxy;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.*;
import org.apache.kafka.clients.consumer.*;
import org.apache.kafka.clients.producer.*;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.apache.kafka.common.serialization.StringSerializer;
import org.springframework.aop.framework.ProxyFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.jdbc.support.JdbcTransactionManager;
import org.springframework.transaction.annotation.AnnotationTransactionAttributeSource;
import org.springframework.transaction.interceptor.TransactionInterceptor;
import tools.jackson.databind.json.JsonMapper;

/** Owned child fixture: production messaging loop and transactional handler, real loopback clients. */
public final class KafkaMessagingCrashProbe {
    static final String BROKERS = "127.0.0.1:9092";
    private static final Json JSON = new Json(JsonMapper.builder().build());

    public static void main(String[] args) {
        try {
            if (args.length != 4) throw new IllegalArgumentException("Expected disposable database, namespace, mode, fault");
            String database = args[0], namespace = args[1], mode = args[2], fault = args[3];
            validateNamespace(namespace);
            if (!Set.of("PUBLISH", "COMPLETE").contains(mode)
                    || !Set.of("NONE", "EARLY_OFFSET", "MISSING_PERSISTENCE").contains(fault)) {
                throw new IllegalArgumentException("Invalid test mode");
            }
            var source = new DriverManagerDataSource(CompletionCrashProbe.jdbcUrl(database),
                    "caseflow_api", CompletionCrashProbe.requiredEnvironment("DB_API_PASSWORD"));
            var db = new JdbcTemplate(source);
            db.setQueryTimeout(10);
            var manager = new JdbcTransactionManager(source);
            var proxy = new ProxyFactory(CompletionCrashProbe.handler(db));
            proxy.setProxyTargetClass(true);
            var interceptor = new TransactionInterceptor();
            interceptor.setTransactionManager(manager);
            interceptor.setTransactionAttributeSource(new AnnotationTransactionAttributeSource());
            proxy.addAdvice(interceptor);
            CompletionHandler handler = (CompletionHandler) proxy.getProxy();
            if (fault.equals("MISSING_PERSISTENCE")) {
                handler = new CompletionHandler(db, null) {
                    @Override public void apply(Map<String, Object> event) { /* Deliberate detector control. */ }
                };
            }
            var completed = new CountDownLatch(1);
            var realProducer = new KafkaProducer<String, String>(producerProperties());
            Producer<String, String> producer = intercept(Producer.class, realProducer, (method, parameters) -> {
                Object result = invoke(method, realProducer, parameters);
                if (mode.equals("PUBLISH") && method.getName().equals("send") && parameters.length == 1) {
                    @SuppressWarnings("unchecked") var future = (Future<RecordMetadata>) result;
                    var record = (ProducerRecord<?, ?>) parameters[0];
                    return new Future<RecordMetadata>() {
                        public boolean cancel(boolean interrupt) { return future.cancel(interrupt); }
                        public boolean isCancelled() { return future.isCancelled(); }
                        public boolean isDone() { return future.isDone(); }
                        public RecordMetadata get() throws InterruptedException, ExecutionException {
                            return reached(future.get());
                        }
                        public RecordMetadata get(long timeout, TimeUnit unit) throws InterruptedException, ExecutionException, TimeoutException {
                            return reached(future.get(timeout, unit));
                        }
                        private RecordMetadata reached(RecordMetadata metadata) {
                            boundary("PUBLISH_ACK", Map.of("topic", metadata.topic(), "partition", metadata.partition(),
                                    "offset", metadata.offset(), "eventId", JSON.object(record.value().toString()).get("eventId")));
                            return metadata;
                        }
                    };
                }
                return result;
            });
            var realConsumer = new KafkaConsumer<String, String>(consumerProperties(namespace + ".consumer"));
            Consumer<String, String> consumer = intercept(Consumer.class, realConsumer, (method, parameters) -> {
                if (method.getName().equals("commitSync") && parameters.length == 1 && parameters[0] instanceof Map<?, ?> offsets) {
                    var entry = offsets.entrySet().iterator().next();
                    var partition = (org.apache.kafka.common.TopicPartition) entry.getKey();
                    var offset = (OffsetAndMetadata) entry.getValue();
                    if (fault.equals("EARLY_OFFSET")) invoke(method, realConsumer, parameters);
                    boundary("COMPLETION_BEFORE_OFFSET", Map.of("topic", partition.topic(), "partition", partition.partition(),
                            "nextOffset", offset.offset()));
                    Object result = fault.equals("EARLY_OFFSET") ? null : invoke(method, realConsumer, parameters);
                    completed.countDown();
                    return result;
                }
                Object result = invoke(method, realConsumer, parameters);
                if (method.getName().equals("poll") && result instanceof ConsumerRecords<?, ?> records) {
                    for (var record : records) {
                        System.out.println("DELIVERED:" + JSON.write(Map.of("topic", record.topic(), "partition", record.partition(),
                                "offset", record.offset(), "eventId", JSON.object(record.value().toString()).get("eventId"))));
                    }
                }
                return result;
            });
            var messaging = new JobMessaging(db, JSON, handler, manager, producer, consumer,
                    namespace + ".jobs", namespace + ".completions", namespace + ".deadletters");
            if (mode.equals("PUBLISH")) {
                messaging.publish();
                realConsumer.close(Duration.ofSeconds(5));
                producer.close(Duration.ofSeconds(5));
            } else {
                messaging.start();
                if (!completed.await(65, TimeUnit.SECONDS)) throw new IllegalStateException("Completion deadline elapsed");
                messaging.stop();
            }
            System.out.println("PROBE_COMPLETED");
        } catch (Throwable failure) {
            System.err.println("PROBE_FAILED:" + failure.getClass().getSimpleName());
            System.exit(2);
        }
    }

    private static void boundary(String name, Map<String, Object> coordinates) {
        var release = new CompletableFuture<String>();
        Thread.ofPlatform().daemon().start(() -> {
            try { release.complete(new BufferedReader(new InputStreamReader(System.in)).readLine()); }
            catch (Exception failure) { release.completeExceptionally(failure); }
        });
        System.out.println("BOUNDARY:" + name + ":" + JSON.write(coordinates));
        System.out.flush();
        try {
            if (!"RELEASE".equals(release.get(45, TimeUnit.SECONDS))) throw new IllegalStateException("Invalid parent command");
        } catch (Exception failure) { throw new IllegalStateException("Parent release deadline", failure); }
    }

    static void validateNamespace(String namespace) {
        if (namespace == null || !namespace.matches("caseflow_test_[a-f0-9]{32}")) {
            throw new IllegalArgumentException("Refusing non-disposable Kafka namespace");
        }
    }

    static Properties producerProperties() {
        var properties = new Properties();
        properties.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, BROKERS);
        properties.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class);
        properties.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class);
        properties.put(ProducerConfig.ACKS_CONFIG, "all");
        properties.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, true);
        properties.put(ProducerConfig.MAX_BLOCK_MS_CONFIG, 10000);
        properties.put(ProducerConfig.DELIVERY_TIMEOUT_MS_CONFIG, 15000);
        properties.put(ProducerConfig.REQUEST_TIMEOUT_MS_CONFIG, 10000);
        return properties;
    }

    static Properties consumerProperties(String group) {
        validateNamespace(group.substring(0, group.indexOf('.')));
        var properties = new Properties();
        properties.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, BROKERS);
        properties.put(ConsumerConfig.GROUP_ID_CONFIG, group);
        properties.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class);
        properties.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class);
        properties.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG, false);
        properties.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest");
        properties.put(ConsumerConfig.DEFAULT_API_TIMEOUT_MS_CONFIG, 10000);
        properties.put(ConsumerConfig.SESSION_TIMEOUT_MS_CONFIG, 6000);
        properties.put(ConsumerConfig.HEARTBEAT_INTERVAL_MS_CONFIG, 1500);
        properties.put(ConsumerConfig.MAX_POLL_RECORDS_CONFIG, 1);
        return properties;
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
