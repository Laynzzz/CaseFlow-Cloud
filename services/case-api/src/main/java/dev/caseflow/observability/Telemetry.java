package dev.caseflow.observability;

import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import io.opentelemetry.api.OpenTelemetry;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.StatusCode;
import io.opentelemetry.api.trace.Tracer;
import io.opentelemetry.api.trace.propagation.W3CTraceContextPropagator;
import io.opentelemetry.context.Context;
import io.opentelemetry.context.Scope;
import io.opentelemetry.context.propagation.TextMapGetter;
import java.util.HashMap;
import java.util.Map;
import org.slf4j.MDC;
import org.springframework.stereotype.Component;

/** Only W3C identifiers cross asynchronous boundaries; never baggage or content. */
@Component
public class Telemetry {
    private static final W3CTraceContextPropagator PROPAGATOR=W3CTraceContextPropagator.getInstance();
    private static final TextMapGetter<Map<String,String>> GETTER=new TextMapGetter<>() {
        public Iterable<String> keys(Map<String,String> carrier) {return carrier.keySet();}
        public String get(Map<String,String> carrier,String key) {return carrier.get(key);}
    };
    private final Tracer tracer;
    private final MeterRegistry metrics;
    public Telemetry(OpenTelemetry telemetry,MeterRegistry metrics) {
        this.tracer=telemetry.getTracer("caseflow-api");this.metrics=metrics;
    }
    public static Telemetry noop() {return new Telemetry(OpenTelemetry.noop(),new SimpleMeterRegistry());}
    public static Map<String,String> capture() {
        var carrier=new HashMap<String,String>();
        PROPAGATOR.inject(Context.current(),carrier,Map::put);
        return sanitize(carrier);
    }
    public static Map<String,String> sanitize(Object value) {
        if(!(value instanceof Map<?,?> map) || !(map.get("traceparent") instanceof String parent)
            || !parent.matches("00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}"))return Map.of();
        var carrier=Map.of("traceparent",parent);
        var context=PROPAGATOR.extract(Context.root(),carrier,GETTER);
        return Span.fromContext(context).getSpanContext().isValid()?carrier:Map.of();
    }
    public WorkSpan span(String operation,Object parent) {
        return new WorkSpan(tracer.spanBuilder(operation)
            .setParent(PROPAGATOR.extract(Context.root(),sanitize(parent),GETTER)).startSpan());
    }
    public void event(String operation,String outcome) {
        metrics.counter("caseflow.messaging.events","operation",operation,"outcome",outcome).increment();
    }
    public static class WorkSpan implements AutoCloseable {
        private final Span span;private final Scope scope;
        private final String oldTrace=MDC.get("traceId"),oldSpan=MDC.get("spanId");
        WorkSpan(Span span) {
            this.span=span;scope=span.makeCurrent();
            if(span.getSpanContext().isValid()) {
                MDC.put("traceId",span.getSpanContext().getTraceId());MDC.put("spanId",span.getSpanContext().getSpanId());
            }
        }
        public void failed() {span.setStatus(StatusCode.ERROR);}
        public void close() {
            scope.close();span.end();
            if(oldTrace==null)MDC.remove("traceId");else MDC.put("traceId",oldTrace);
            if(oldSpan==null)MDC.remove("spanId");else MDC.put("spanId",oldSpan);
        }
    }
}
