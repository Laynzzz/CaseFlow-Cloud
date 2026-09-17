"""Exercise the pinned collector with synthetic content in an owned disposable container."""
from pathlib import Path
import argparse
import json
import subprocess
import time
import urllib.request
from uuid import uuid4

IMAGE = 'otel/opentelemetry-collector-contrib:0.161.0@sha256:fd328de2552466ad78385e1b1289c3f2402b1c45f265b252aab1955b42845ac1'


def verify(output):
    output.mkdir(parents=True, exist_ok=True)
    config = Path(__file__).with_name('collector.yaml').read_text()
    config = config[:config.index('exporters:')] + '''exporters:
  file:
    path: /output/sanitized.json
service:
  telemetry:
    logs:
      level: warn
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, filter/unsupported_content, transform/metadata_only, batch]
      exporters: [file]
'''
    (output / 'collector-probe.yaml').write_text(config)
    sanitized = output / 'sanitized.json'
    # Only replace this invocation's known output file, never a directory tree.
    if sanitized.exists():
        sanitized.unlink()
    name = 'caseflow_observability_test_' + uuid4().hex
    created = False
    try:
        result = subprocess.run(['docker', 'run', '-d', '--name', name,
                                 '-p', '127.0.0.1::4318', '--mount',
                                 f'type=bind,source={output.resolve()},target=/output',
                                 IMAGE, '--config=/output/collector-probe.yaml'],
                                capture_output=True, text=True, check=True)
        created = True
        assert result.stdout.strip()
        port = subprocess.check_output(['docker', 'port', name, '4318/tcp'], text=True).strip().split(':')[-1]
        now = time.time_ns()
        sentinel = 'synthetic-private-config-probe'
        def attrs(values):
            return [{'key': key, 'value': {'stringValue': value}} for key, value in values.items()]
        spans = []
        for index, span_name in enumerate(('worker.execute', 'GET /private/' + sentinel, 'worker.publish')):
            span = {'traceId': '1' * 32, 'spanId': f'{index + 2:016x}', 'parentSpanId': '1' * 16,
                    'name': span_name, 'kind': 1, 'startTimeUnixNano': str(now),
                    'endTimeUnixNano': str(now + 1000), 'traceState': sentinel,
                    'attributes': attrs({'job.kind': 'DOCUMENT', 'outcome': 'succeeded',
                                         'url.full': 'https://example.invalid/?secret=' + sentinel,
                                         'authorization': sentinel, 'purchase.description': sentinel}),
                    'status': {'code': 2, 'message': sentinel},
                    'events': [{'timeUnixNano': str(now), 'name': sentinel,
                                'attributes': attrs({'exception.message': sentinel})}]}
            if index == 2:
                span['links'] = [{'traceId': 'a' * 32, 'spanId': 'b' * 16,
                                 'attributes': attrs({'secret': sentinel})}]
            spans.append(span)
        payload = {'resourceSpans': [{'resource': {'attributes': attrs({'service.name': 'case-worker', 'secret': sentinel})},
                                     'scopeSpans': [{'scope': {'name': 'caseflow-worker',
                                                               'attributes': attrs({'secret': sentinel})},
                                                     'spans': spans}]}]}
        data = json.dumps(payload).encode()
        deadline = time.monotonic() + 15
        while True:
            try:
                request = urllib.request.Request('http://127.0.0.1:' + port + '/v1/traces', data=data,
                                                 headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(request, timeout=2) as response:
                    assert response.status == 200
                break
            except Exception:
                if time.monotonic() >= deadline:
                    raise AssertionError('Collector rejected synthetic probe; inspect owned log') from None
                time.sleep(.2)
        deadline = time.monotonic() + 10
        while not (sanitized.exists() and sanitized.stat().st_size) and time.monotonic() < deadline:
            time.sleep(.2)
        assert sanitized.exists() and sanitized.stat().st_size, 'No transformed spans exported'
        content = sanitized.read_text()
        if sentinel in content:
            raise AssertionError('Synthetic privacy sentinel leaked')
        exported = json.loads(content.splitlines()[0])
        emitted = exported['resourceSpans'][0]['scopeSpans'][0]['spans']
        assert len(emitted) == 2
        assert [span['name'] for span in emitted] == ['worker.execute', 'caseflow.operation']
        assert all(span['traceId'] == '1' * 32 and span['parentSpanId'] == '1' * 16 for span in emitted)
        assert all(not span.get('events') and not span.get('links') for span in emitted)
        for span in emitted:
            assert {attribute['key'] for attribute in span['attributes']} == {'job.kind', 'outcome'}
        proof = dict(spans_sent=3, spans_exported=2, sentinel_absent=True, fixed_name_retained=True,
                     dynamic_name_normalized=True, trace_parent_preserved=True, events_removed=True,
                     unsupported_linked_span_dropped=True, image=IMAGE)
        (output / 'collector-privacy-proof.json').write_text(json.dumps(proof, indent=2) + '\n')
        print(json.dumps(proof))
    finally:
        if created:
            try:
                with (output / 'collector-probe.txt').open('w') as log:
                    subprocess.run(['docker', 'logs', name], stdout=log, stderr=subprocess.STDOUT, check=True)
            finally:
                subprocess.run(['docker', 'rm', '-f', name], capture_output=True, check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    verify(parser.parse_args().output.resolve())
