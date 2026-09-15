package dev.caseflow.documents;

import dev.caseflow.common.Json;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.apache.kafka.clients.consumer.*;
import org.apache.kafka.clients.producer.*;
import org.apache.kafka.common.errors.WakeupException;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.apache.kafka.common.serialization.StringSerializer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

@Service
@EnableScheduling
public class JobMessaging {
    private static final Logger LOG=LoggerFactory.getLogger(JobMessaging.class);
    private final JdbcTemplate db;private final Json json;private final CompletionHandler completion;
    private final TransactionTemplate transaction;private final KafkaProducer<String,String> producer;
    private final KafkaConsumer<String,String> consumer;
    private volatile boolean running=true;private Thread thread;
    public JobMessaging(JdbcTemplate db,Json json,CompletionHandler completion,PlatformTransactionManager manager,
                        @Value("${KAFKA_BOOTSTRAP_SERVERS:127.0.0.1:9092}") String brokers) {
        this.db=db;this.json=json;this.completion=completion;transaction=new TransactionTemplate(manager);
        var producerOptions=new Properties();producerOptions.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG,brokers);
        producerOptions.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG,StringSerializer.class);
        producerOptions.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG,StringSerializer.class);
        producerOptions.put(ProducerConfig.ACKS_CONFIG,"all");producerOptions.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG,true);
        producerOptions.put(ProducerConfig.DELIVERY_TIMEOUT_MS_CONFIG,15000);producerOptions.put(ProducerConfig.REQUEST_TIMEOUT_MS_CONFIG,10000);
        producerOptions.put(ProducerConfig.MAX_BLOCK_MS_CONFIG,10000);
        producer=new KafkaProducer<>(producerOptions);
        var consumerOptions=new Properties();consumerOptions.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG,brokers);
        consumerOptions.put(ConsumerConfig.GROUP_ID_CONFIG,"caseflow-api-completion-v1");
        consumerOptions.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG,false);consumerOptions.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG,"earliest");
        consumerOptions.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG,StringDeserializer.class);
        consumerOptions.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG,StringDeserializer.class);
        consumerOptions.put(ConsumerConfig.MAX_POLL_RECORDS_CONFIG,20);consumer=new KafkaConsumer<>(consumerOptions);
    }
    @PostConstruct void start() {
        thread=new Thread(this::consume,"completion-consumer");thread.setDaemon(true);thread.start();
    }
    @Scheduled(fixedDelay=500)
    public void publish() {
        try {
            transaction.executeWithoutResult(tx->{
                var rows=db.queryForList("SELECT * FROM core.outbox WHERE published_at IS NULL ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1");
                if(rows.isEmpty())return;var row=rows.getFirst();
                try {
                    producer.send(new ProducerRecord<>("caseflow.jobs.v1",row.get("tenant_id")+":"+row.get("case_id"),row.get("payload").toString())).get(20,TimeUnit.SECONDS);
                } catch(Exception e) {throw new IllegalStateException("Broker acknowledgement unavailable",e);}
                db.update("UPDATE core.outbox SET published_at=now() WHERE event_id=?",row.get("event_id"));
            });
        }catch(Exception e){LOG.warn("outbox_publish_retry error_type={}",e.getClass().getSimpleName());}
    }
    private void consume() {
        consumer.subscribe(List.of("caseflow.completions.v1"));
        try {
            while(running) {
                ConsumerRecords<String,String> records;
                try {records=consumer.poll(Duration.ofSeconds(1));}
                catch(WakeupException e){if(!running)break;throw e;}
                for(var record:records) {
                    while(running) {
                        try {
                            try {completion.apply(json.object(record.value()));}
                            catch(IllegalArgumentException|NullPointerException|ClassCastException e) {
                                var dead=Map.of("reason","INVALID_COMPLETION_ENVELOPE","topic",record.topic(),"partition",record.partition(),"offset",record.offset(),"hash",json.hash(record.value()));
                                producer.send(new ProducerRecord<>("caseflow.deadletters.v1","invalid-completion",json.write(dead))).get(20,TimeUnit.SECONDS);
                            }
                            consumer.commitSync(Map.of(new org.apache.kafka.common.TopicPartition(record.topic(),record.partition()),new OffsetAndMetadata(record.offset()+1)));
                            break;
                        } catch(Exception e) {
                            LOG.warn("completion_retry error_type={}",e.getClass().getSimpleName());
                            try {Thread.sleep(2000);}catch(InterruptedException interrupted){Thread.currentThread().interrupt();return;}
                        }
                    }
                }
            }
        }finally{consumer.close();}
    }
    @PreDestroy void stop() throws InterruptedException {
        running=false;consumer.wakeup();if(thread!=null)thread.join(25000);producer.close(Duration.ofSeconds(5));
    }
}
