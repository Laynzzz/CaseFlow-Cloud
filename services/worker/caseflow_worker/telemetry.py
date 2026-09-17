"""Metadata-only traces and fixed-label metrics; telemetry never contains input text."""
import os
import re
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest
from prometheus_client.core import GaugeMetricFamily
from .settings import database
from .kafka_metrics import KafkaMetrics

tracer = trace.NoOpTracerProvider().get_tracer("caseflow-worker")
provider = None
propagator = TraceContextTextMapPropagator()
registry = CollectorRegistry()
queue_seconds = Histogram("caseflow_job_queue_seconds", "Ready-to-claim duration, excluding deliberate retry backoff",
                          ["kind"], registry=registry, buckets=(.1,.5,1,2,5,10,30,60,120,300))
execution_seconds = Histogram("caseflow_job_execution_seconds", "Execution and result persistence duration",
                              ["kind","outcome"], registry=registry, buckets=(.1,.5,1,2,5,10,30,60,120,300))
events = Counter("caseflow_worker_events", "Worker outcomes; fixed operation and outcome labels",
                 ["operation","outcome"], registry=registry)


def configure():
    global tracer, provider
    if provider is not None:
        return
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
    rate = max(0, min(1, float(os.getenv("CASEFLOW_TRACE_SAMPLE_RATE", "0.1"))))
    provider = TracerProvider(resource=Resource.create({"service.name": "case-worker"}),
                              sampler=ParentBased(TraceIdRatioBased(rate)))
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").rstrip("/")
    if endpoint and os.getenv("OTEL_TRACES_EXPORTER", "none") == "otlp":
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint+"/v1/traces", timeout=2)))
    tracer = provider.get_tracer("caseflow-worker")


def close():
    global provider, tracer
    if provider is not None:
        provider.shutdown()
    provider = None
    tracer = trace.NoOpTracerProvider().get_tracer("caseflow-worker")


def sanitize(carrier):
    value = carrier.get("traceparent", "") if isinstance(carrier, dict) else ""
    if not isinstance(value, str) or not re.fullmatch(r"00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}", value):
        return {}
    result = {"traceparent": value}
    if not trace.get_current_span(propagator.extract(result)).get_span_context().is_valid:
        return {}
    return result


def capture():
    carrier = {}
    propagator.inject(carrier)
    return sanitize(carrier)


def correlation():
    context = trace.get_current_span().get_span_context()
    return {"trace_id": format(context.trace_id, "032x"), "span_id": format(context.span_id, "016x")} if context.is_valid else {}


@contextmanager
def span(operation, parent=None):
    context = propagator.extract(sanitize(parent), context=Context()) if parent is not None else None
    # Disable automatic exception recording: messages/stack locals can contain purchase text.
    with tracer.start_as_current_span(operation, context=context, record_exception=False,
                                      set_status_on_exception=False) as current:
        try:
            yield current
        except Exception:
            current.set_status(trace.StatusCode.ERROR)
            raise


class DatabaseMetrics:
    def describe(self):
        return []  # Registration never queries the database.

    def collect(self):
        up = GaugeMetricFamily("caseflow_metrics_database_up", "Latest operational database collection succeeded")
        try:
            with database() as db:
                db.execute("SET LOCAL statement_timeout='2000ms'")
                grouped = db.execute("SELECT kind,status,count(*) AS n FROM worker.jobs GROUP BY kind,status").fetchall()
                signals = db.execute("""SELECT
                    coalesce(max(extract(epoch FROM now()-available_at)) FILTER
                      (WHERE status IN ('QUEUED','RETRY_WAIT') AND available_at<=now()),0) AS oldest,
                    count(*) FILTER (WHERE status='RUNNING' AND lease_until<now()) AS expired
                    FROM worker.jobs""").fetchone()
                outboxes = db.execute("""SELECT 'case-worker' AS service,count(*) AS n,
                    coalesce(max(extract(epoch FROM now()-created_at)),0) AS age
                    FROM worker.outbox WHERE published_at IS NULL
                    UNION ALL SELECT 'case-api',count(*),coalesce(max(extract(epoch FROM now()-observed_at)),0)
                    FROM core.worker_operation_signals WHERE kind='API_OUTBOX_PENDING'""").fetchall()
                ai = db.execute("""SELECT state,count(*) AS n,coalesce(sum(actual_usd),0) AS actual,
                    coalesce(sum(reserved_usd),0) AS reserved,coalesce(sum(input_tokens),0) AS input,
                    coalesce(sum(output_tokens),0) AS output,
                    coalesce(sum(elapsed_ms),0)/1000.0 AS elapsed FROM worker.ai_calls GROUP BY state""").fetchall()
        except Exception:
            up.add_metric([], 0)
            yield up
            return
        up.add_metric([], 1)
        yield up
        counts = GaugeMetricFamily("caseflow_jobs", "Durable jobs by bounded kind and state", labels=["kind","status"])
        for row in grouped:
            counts.add_metric([row["kind"],row["status"]],row["n"])
        yield counts
        for name, key, description in (("caseflow_oldest_ready_job_seconds","oldest","Oldest eligible job age"),
                                       ("caseflow_expired_leases","expired","Expired running leases")):
            metric = GaugeMetricFamily(name, description)
            metric.add_metric([], float(signals[key]))
            yield metric
        for name, key in (("caseflow_outbox_pending","n"),("caseflow_outbox_oldest_seconds","age")):
            metric = GaugeMetricFamily(name, "Durable unpublished outbox metadata", labels=["service"])
            for row in outboxes:
                metric.add_metric([row["service"]],float(row[key]))
            yield metric
        for name, key in (("caseflow_ai_calls","n"),("caseflow_ai_actual_usd","actual"),
                          ("caseflow_ai_reserved_usd","reserved"),("caseflow_ai_input_tokens","input"),
                          ("caseflow_ai_output_tokens","output"),("caseflow_ai_model_seconds_sum","elapsed")):
            metric = GaugeMetricFamily(name, "Durable lifetime AI ledger; unknown usage remains reserved", labels=["state"])
            for row in ai:
                metric.add_metric([row["state"]],float(row[key]))
            yield metric


registry.register(DatabaseMetrics())
registry.register(KafkaMetrics())


def render_metrics():
    return generate_latest(registry)
