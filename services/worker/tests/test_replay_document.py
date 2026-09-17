"""Offline checks for the bounded local broker replay evidence tool."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "tools/replay_document.py"


def test_import_needs_no_credentials_dependencies_or_network():
    code = ("import runpy; runpy.run_path(" + repr(str(SCRIPT)) + ")")
    result = subprocess.run([sys.executable, "-S", "-c", code], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


@pytest.fixture
def replay():
    spec = importlib.util.spec_from_file_location("replay_document", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_rejects_unbounded_counts_timeouts_and_requires_evidence(replay):
    for args in (["--count", "0"], ["--count", "5001"], ["--count", "-1"],
                 ["--timeout", "nan"], ["--timeout", "inf"], ["--timeout", "0"],
                 ["--timeout", "3601"]):
        with pytest.raises(SystemExit):
            replay.parse_args(["--output", "unused.json", *args])
    with pytest.raises(SystemExit):
        replay.parse_args([])
    assert replay.parse_args(["--output", "unused.json"]).count == 10
    assert replay.parse_args(["--output", "unused.json", "--count", "5000"]).count == 5000


def test_fixture_rejects_extra_fields_and_noncanonical_ids(replay):
    valid = dict(tenantId="11111111-1111-4111-8111-111111111111",
                 caseId="22222222-2222-4222-8222-222222222222",
                 jobId="33333333-3333-4333-8333-333333333333")
    assert replay.validate_fixture(valid) == valid
    for bad in ({**valid, "password": "not-allowed"}, {**valid, "jobId": "../other"},
                {**valid, "tenantId": None}):
        with pytest.raises(ValueError):
            replay.validate_fixture(bad)


def test_offset_proof_requires_each_acknowledged_partition_next_offset(replay):
    acks = [dict(topic="caseflow.jobs.v1", partition=0, offset=11),
            dict(topic="caseflow.jobs.v1", partition=0, offset=13),
            dict(topic="caseflow.completions.v1", partition=1, offset=7)]
    bounds = replay.delivery_boundaries(acks)
    assert bounds == [dict(topic="caseflow.completions.v1", partition=1, first=7, last=7,
                           acknowledged=1, requiredCommitted=8, group="caseflow-api-completion-v1"),
                      dict(topic="caseflow.jobs.v1", partition=0, first=11, last=13,
                           acknowledged=2, requiredCommitted=14, group="caseflow-worker-v1")]
    commits = [dict(topic="caseflow.completions.v1", partition=1, group="caseflow-api-completion-v1", offset=8, error=None),
               dict(topic="caseflow.jobs.v1", partition=0, group="caseflow-worker-v1", offset=14, error=None)]
    assert replay.offsets_reached(bounds, commits)
    for bad in (commits[:1], [{**commits[0], "offset": 7}, commits[1]],
                [commits[0], {**commits[1], "error": "BROKER_ERROR"}],
                [commits[0], {**commits[1], "group": "wrong-group"}]):
        assert not replay.offsets_reached(bounds, bad)
    assert not replay.offsets_reached([], [])


def test_acknowledgement_rejects_invalid_broker_coordinates(replay):
    for ack in (dict(topic="other", partition=0, offset=2),
                dict(topic="caseflow.jobs.v1", partition=0, offset=-1)):
        with pytest.raises(ValueError):
            replay.delivery_boundaries([ack])


def test_report_is_reserved_exclusively_and_failure_is_redacted(replay, tmp_path, monkeypatch):
    path = tmp_path / "report.json"
    def fail(*_):
        raise RuntimeError("secret-password raw purchase data")
    monkeypatch.setattr(replay, "run_probe", fail)
    assert replay.main(["--output", str(path)]) == 1
    report = json.loads(path.read_text())
    assert report["status"] == "FAILED"
    assert report["error"]["type"] == "RuntimeError"
    assert "secret-password" not in path.read_text()
    before = path.read_bytes()
    assert replay.main(["--output", str(path)]) == 2
    assert path.read_bytes() == before


def test_invalid_fixture_failure_leaves_evidence_before_broker_access(replay, tmp_path, monkeypatch):
    fixture = tmp_path / "invalid.json"
    fixture.write_text('{"jobId":"broken"}')
    monkeypatch.setattr(replay, "FIXTURE", fixture)
    path = tmp_path / "failed.json"
    assert replay.main(["--output", str(path)]) == 1
    report = json.loads(path.read_text())
    assert report["acknowledgements"] == []
    assert report["status"] == "FAILED"


def test_baseline_and_final_require_exact_selected_result_and_business_state(replay):
    fixture = dict(tenantId="11111111-1111-4111-8111-111111111111",
                   caseId="22222222-2222-4222-8222-222222222222",
                   jobId="33333333-3333-4333-8333-333333333333")
    baseline = dict(core_status="SUCCEEDED", worker_status="SUCCEEDED", business_state="APPROVED",
                    document_status="SUCCEEDED", generation_id=fixture["jobId"], core_attempt=1,
                    worker_attempt=1, core_fence=2, worker_fence=2, core_input_hash="a" * 64,
                    worker_input_hash="a" * 64, artifact_count=1, success_audits=1, failure_audits=0,
                    artifact=dict(attempt=1, fence=2, sha256="b" * 64, byte_size=30,
                      object_key="tenants/11111111-1111-4111-8111-111111111111/documents/33333333-3333-4333-8333-333333333333/attempt-1/fence-2/44444444-4444-4444-8444-444444444444.docx"))
    assert all(replay.state_assertions(baseline, fixture).values())
    for field, value in (("artifact_count", 2), ("success_audits", 0), ("failure_audits", 1),
                         ("core_status", "FAILED"), ("worker_attempt", 2), ("core_fence", 3),
                         ("generation_id", fixture["caseId"]), ("worker_input_hash", "x" * 64)):
        assert not all(replay.state_assertions({**baseline, field: value}, fixture).values())
    changed = copy.deepcopy(baseline)
    changed["artifact"]["object_key"] += "/../other"
    assert not all(replay.state_assertions(changed, fixture).values())
    assert replay.final_assertions(baseline, baseline, fixture, "STALE")["unchanged"]
    changed = copy.deepcopy(baseline)
    changed["artifact"]["sha256"] = "c" * 64
    assert not replay.final_assertions(baseline, changed, fixture, "STALE")["unchanged"]
    assert not replay.final_assertions(baseline, baseline, fixture, "APPLIED")["lateFailureStale"]


def test_delivery_proof_rejects_repeated_ack_coordinate(replay):
    ack = dict(topic="caseflow.jobs.v1", partition=0, offset=4)
    with pytest.raises(ValueError, match="DUPLICATE_ACKNOWLEDGEMENT"):
        replay.delivery_boundaries([ack, ack])


def test_event_validation_rejects_cross_scope_hash_and_unpublished_original(replay):
    fixture = dict(tenantId="11111111-1111-4111-8111-111111111111",
                   caseId="22222222-2222-4222-8222-222222222222",
                   jobId="33333333-3333-4333-8333-333333333333")
    state = dict(core_attempt=1, core_fence=2, core_input_hash="a" * 64)
    event = dict(eventId="44444444-4444-4444-8444-444444444444", eventType="document.requested",
                 tenantId=fixture["tenantId"], aggregateId=fixture["caseId"], jobId=fixture["jobId"],
                 aggregateType="case", schemaVersion=1, attempt=1, inputHash="a" * 64)
    request = dict(event_id=event["eventId"], payload=event, published=True, received=True)
    success = dict(event_id="55555555-5555-4555-8555-555555555555", published=True, disposition="APPLIED",
                   payload={**event, "eventId": "55555555-5555-4555-8555-555555555555",
                            "eventType": "document.succeeded", "status": "SUCCEEDED", "fence": 2})

    class Database:
        def __init__(self, request_row, success_row):
            self.rows = iter(([request_row], [success_row]))

        def execute(self, query, parameters):
            assert "WHERE tenant_id=%s" in query
            assert parameters[0] == fixture["tenantId"]
            return SimpleNamespace(fetchall=lambda: next(self.rows))

    assert replay.validate_events(Database(request, success), fixture, state) == (event, success["payload"])
    for key, value in (("tenantId", fixture["caseId"]), ("inputHash", "b" * 64), ("eventId", fixture["jobId"]),
                       ("aggregateId", fixture["jobId"]), ("attempt", 2)):
        bad = {**request, "payload": {**event, key: value}}
        with pytest.raises(ValueError):
            replay.validate_events(Database(bad, success), fixture, state)
    with pytest.raises(ValueError):
        replay.validate_events(Database({**request, "published": False}, success), fixture, state)


def test_delivery_records_callbacks_and_flushes_with_bounded_backpressure(replay):
    class Producer:
        def __init__(self):
            self.pending = []
            self.first = True
            self.offset = 40

        def produce(self, topic, *, key, value, on_delivery):
            assert key == "tenant:case"
            if self.first:
                self.first = False
                raise BufferError()
            self.pending.append((topic, on_delivery))

        def poll(self, seconds):
            assert 0 <= seconds <= .1

        def flush(self, seconds):
            assert 0 < seconds <= 20
            for topic, callback in self.pending:
                self.offset += 1
                message = SimpleNamespace(topic=lambda: topic, partition=lambda: 0, offset=lambda: self.offset)
                callback(None, message)
            self.pending.clear()
            return 0

    report = dict(acknowledgements=[], deliveryErrors=[], enqueued=0)
    replay.produce_events(Producer(), "tenant:case", {"eventId": "request"}, {"eventId": "success"},
                          {"eventId": "late"}, 2, time.monotonic() + 5, report, lambda: None)
    assert report["enqueued"] == 5
    assert len(report["acknowledgements"]) == 5
    assert report["acknowledgements"][-1] == dict(topic="caseflow.completions.v1", partition=0, offset=45)
    assert report["unflushed"] == 0
    assert all(report["deliveryAssertions"].values())


def test_delivery_error_and_permanent_backpressure_fail_with_evidence(replay):
    class FailedProducer:
        def produce(self, topic, *, key, value, on_delivery):
            on_delivery(SimpleNamespace(code=lambda: -1, name=lambda: "DELIVERY_FAILED"), None)

        def poll(self, seconds):
            pass

        def flush(self, seconds):
            return 0

    report = dict(acknowledgements=[], deliveryErrors=[], enqueued=0)
    with pytest.raises(RuntimeError, match="BROKER_DELIVERY_FAILED"):
        replay.produce_events(FailedProducer(), "tenant:case", {}, {}, {}, 1,
                              time.monotonic() + 5, report, lambda: None)
    assert report["deliveryErrors"] == [dict(code=-1, name="DELIVERY_FAILED")]
    assert report["enqueued"] == 1

    class FullProducer(FailedProducer):
        def produce(self, *args, **kwargs):
            raise BufferError()

        def poll(self, seconds):
            time.sleep(seconds)

    report = dict(acknowledgements=[], deliveryErrors=[], enqueued=0)
    with pytest.raises(TimeoutError):
        replay.produce_events(FullProducer(), "tenant:case", {}, {}, {}, 1,
                              time.monotonic() + .02, report, lambda: None)
    assert report["enqueued"] == 0


def test_committed_reader_never_joins_or_changes_the_application_group(replay, monkeypatch):
    class ReadOnlyConsumer:
        def committed(self, partitions, timeout):
            assert 0 < timeout <= 5
            assert [(p.topic, p.partition) for p in partitions] == [("caseflow.jobs.v1", 2)]
            return [SimpleNamespace(topic="caseflow.jobs.v1", partition=2, offset=9, error=None)]

        def __getattr__(self, name):
            pytest.fail(f"Unexpected group operation: {name}")

    result = replay.read_committed({"caseflow-worker-v1": ReadOnlyConsumer()},
        [dict(group="caseflow-worker-v1", topic="caseflow.jobs.v1", partition=2)], time.monotonic() + 5)
    assert result == [dict(group="caseflow-worker-v1", topic="caseflow.jobs.v1", partition=2, offset=9, error=None)]
