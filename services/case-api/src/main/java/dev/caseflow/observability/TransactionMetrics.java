package dev.caseflow.observability;

import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.config.BeanPostProcessor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.transaction.ConfigurableTransactionManager;
import org.springframework.transaction.TransactionExecution;
import org.springframework.transaction.TransactionExecutionListener;

/** Observe actual transaction outcomes without changing transaction boundaries. */
@Configuration
public class TransactionMetrics {
    @Bean static BeanPostProcessor transactionMetricsListener(ObjectProvider<MeterRegistry> registries) {
        return new BeanPostProcessor() {
            @Override public Object postProcessAfterInitialization(Object bean,String name) {
                if(bean instanceof ConfigurableTransactionManager manager) {
                    manager.addListener(new TransactionExecutionListener() {
                        private void record(String outcome) {
                            var registry=registries.getIfAvailable();
                            if(registry!=null)registry.counter("caseflow.db.transactions","outcome",outcome).increment();
                        }
                        @Override public void afterBegin(TransactionExecution transaction,Throwable failure) {
                            if(failure!=null)record("begin_failed");
                        }
                        @Override public void afterCommit(TransactionExecution transaction,Throwable failure) {
                            record(failure==null?"committed":"commit_failed");
                        }
                        @Override public void afterRollback(TransactionExecution transaction,Throwable failure) {
                            record(failure==null?"rolled_back":"rollback_failed");
                        }
                    });
                }
                return bean;
            }
        };
    }
}
