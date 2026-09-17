from uuid import uuid4

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from caseflow_worker import jobs, telemetry
from caseflow_worker.settings import database


@pytest.fixture
def spans(monkeypatch):
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(telemetry, "tracer", provider.get_tracer("caseflow-test"))
    yield exporter
    provider.shutdown()


def test_trace_context_survives_durable_job_and_completion(event, spans):
    with telemetry.span("request"):
        context = telemetry.capture()
    assert context.get("traceparent")
    event = event.model_copy(update={"traceContext": {**context, "baggage": "SECRET"}})
    jobs.schedule(event)
    jobs.schedule(event.model_copy(update={"eventId": uuid4(), "traceContext": {}}))
    job = jobs.claim(uuid4())
    assert job["trace_context"] == context
    with telemetry.span("execute", job["trace_context"]):
        child = telemetry.capture()
        jobs.finish(job, {"key": "synthetic/trace", "sha256": "b"*64, "size": 100})
    with database() as db:
        payload = db.execute("SELECT payload FROM worker.outbox WHERE payload->>'status'='SUCCEEDED'").fetchone()["payload"]
    assert payload["traceContext"] == child
    request, execute = spans.get_finished_spans()
    assert request.context.trace_id == execute.context.trace_id
    assert execute.parent.span_id == request.context.span_id
    assert "SECRET" not in str(payload)


def test_invalid_context_and_exception_content_not_exported(spans):
    assert telemetry.sanitize({"traceparent": "invalid", "authorization": "SECRET"}) == {}
    with pytest.raises(ValueError), telemetry.span("execute", {"traceparent": "invalid"}):
        raise ValueError("SECRET purchase text")
    span = spans.get_finished_spans()[0]
    assert not span.events
    assert span.status.description is None
    assert "SECRET" not in str(span.attributes)


def test_metrics_failure_is_unhealthy_not_zero_backlog(monkeypatch):
    def unavailable():
        raise RuntimeError("SECRET database details")
    monkeypatch.setattr(telemetry, "database", unavailable)
    data = telemetry.render_metrics().decode()
    assert "caseflow_metrics_database_up 0.0" in data
    assert "caseflow_jobs{" not in data
    assert "SECRET" not in data


def test_metrics_have_bounded_labels_and_real_job_state(event):
    jobs.schedule(event)
    data = telemetry.render_metrics().decode()
    assert 'caseflow_jobs{kind="DOCUMENT",status="QUEUED"} 1.0' in data
    assert str(event.tenantId) not in data
    assert str(event.jobId) not in data


def test_reclaimed_lease_queue_starts_at_expiry_not_original_availability(event, isolated_database):
    import psycopg
    jobs.schedule(event)
    jobs.claim(uuid4())
    with psycopg.connect(**isolated_database) as db:
        db.execute("UPDATE worker.jobs SET available_at=now()-interval '1 hour',lease_until=now()-interval '2 seconds'")
    reclaimed = jobs.claim(uuid4())
    assert 2 <= (reclaimed["updated_at"]-reclaimed["ready_at"]).total_seconds() < 10
    assert (reclaimed["updated_at"]-reclaimed["available_at"]).total_seconds() >= 3600


def test_export_disabled_still_propagates_without_creating_network_exporter(monkeypatch):
    import opentelemetry.exporter.otlp.proto.http.trace_exporter as exporter
    def forbidden(*args, **kwargs):
        pytest.fail("Exporter must not be constructed without explicit opt-in")
    monkeypatch.setattr(exporter, "OTLPSpanExporter", forbidden)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:9")
    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "none")
    telemetry.close()
    try:
        telemetry.configure()
        with telemetry.span("worker.execute"):
            assert telemetry.capture().get("traceparent")
    finally:
        telemetry.close()
