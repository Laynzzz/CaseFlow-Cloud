package dev.caseflow.observability;

import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import io.opentelemetry.sdk.OpenTelemetrySdk;
import io.opentelemetry.sdk.testing.exporter.InMemorySpanExporter;
import io.opentelemetry.sdk.trace.SdkTracerProvider;
import io.opentelemetry.sdk.trace.export.SimpleSpanProcessor;
import java.util.Map;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class TelemetryTest {
    @Test void persistedParentConnectsNewThreadSpanWithoutBaggage() {
        var exporter=InMemorySpanExporter.create();
        try(var provider=SdkTracerProvider.builder().addSpanProcessor(SimpleSpanProcessor.create(exporter)).build()) {
            var telemetry=new Telemetry(OpenTelemetrySdk.builder().setTracerProvider(provider).build(),new SimpleMeterRegistry());
            Map<String,String> parent;
            try(var span=telemetry.span("api.publish",Map.of())) { parent=Telemetry.capture(); }
            assertTrue(parent.containsKey("traceparent"));
            try(var span=telemetry.span("api.complete",Map.of("traceparent",parent.get("traceparent"),"baggage","SECRET"))) {
                assertNotEquals(parent,Telemetry.capture());
                span.failed();
            }
            var spans=exporter.getFinishedSpanItems();
            assertEquals(spans.get(0).getTraceId(),spans.get(1).getTraceId());
            assertEquals(spans.get(0).getSpanId(),spans.get(1).getParentSpanId());
            assertTrue(spans.get(1).getEvents().isEmpty());
            assertEquals("",spans.get(1).getStatus().getDescription());
            assertEquals(Map.of(),Telemetry.sanitize(Map.of("traceparent","invalid","authorization","SECRET")));
            assertEquals(Map.of(),Telemetry.capture());
        }
    }
}
