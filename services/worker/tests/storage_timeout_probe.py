"""Owned loopback HTTP endpoint that withholds responses to real SDK requests."""
from contextlib import contextmanager
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
import threading
import time
from types import SimpleNamespace
from urllib.parse import unquote, urlsplit

import boto3
from botocore.config import Config
from botocore.exceptions import ReadTimeoutError

from caseflow_worker.settings import BUCKET
from process_probe import guard_database


@contextmanager
def storage_timeout(upstream, event, boundary):
    guard_database()
    if boundary not in {'template-read', 'upload-response'}:
        raise ValueError('unknown storage timeout boundary')
    if (os.getenv('S3_ENDPOINT', 'http://127.0.0.1:8333') != 'http://127.0.0.1:8333'
            or BUCKET != 'caseflow-local' or upstream.meta.endpoint_url != 'http://127.0.0.1:8333'):
        raise ValueError('timeout probe requires local fixture storage')
    expected_prefix = f'tenants/{event.tenantId}/documents/{event.jobId}/'
    release = threading.Event()
    state = SimpleNamespace(received=threading.Event(), uploaded=None, errors=[], timeouts=[],
                            upload_acknowledged_at=None, timed_out_at=None)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # Request signatures and paths do not belong in server logs.

        def do_GET(self):
            state.received.set()
            if boundary != 'template-read':
                state.errors.append('unexpected_get')
            release.wait(5)  # No HTTP status or body: SDK must time out on the socket.

        def do_PUT(self):
            state.received.set()
            try:
                if boundary != 'upload-response':
                    raise ValueError('unexpected_put')
                path = unquote(urlsplit(self.path).path)
                prefix = '/' + BUCKET + '/'
                if not path.startswith(prefix):
                    raise ValueError('unexpected_bucket')
                key = path[len(prefix):]
                if not key.startswith(expected_prefix) or self.headers.get('If-None-Match') != '*':
                    raise ValueError('unexpected_object_reference')
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 10 * 1024 * 1024 or self.headers.get('Transfer-Encoding'):
                    raise ValueError('unexpected_body_encoding')
                self.connection.settimeout(3)
                body = self.rfile.read(size)
                if len(body) != size:
                    raise ValueError('incomplete_body')
                # The actual local S3 service durably accepts bytes; suppress its acknowledgement.
                upstream.put_object(Bucket=BUCKET, Key=key, Body=body, IfNoneMatch='*',
                                    ContentType=self.headers['Content-Type'])
                state.uploaded = dict(key=key, sha256=sha256(body).hexdigest(), size=size)
                state.upload_acknowledged_at = time.monotonic()
            except Exception as error:
                state.errors.append(type(error).__name__)
            release.wait(5)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = False
    serving = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
    serving.start()
    # Synthetic signing credentials are used only against this owned endpoint.
    stalled = boto3.client('s3', endpoint_url=f'http://127.0.0.1:{server.server_port}',
                           region_name='us-east-1', aws_access_key_id='synthetic-test',
                           aws_secret_access_key='synthetic-test-only',
                           config=Config(connect_timeout=1, read_timeout=1,
                                         retries={'total_max_attempts': 1},
                                         request_checksum_calculation='when_required',
                                         s3={'addressing_style': 'path'}))

    def timed_call(method, kwargs):
        try:
            return getattr(stalled, method)(**kwargs)
        except ReadTimeoutError as error:
            state.timeouts.append(type(error).__name__)
            state.timed_out_at = time.monotonic()
            raise

    class Client:
        def get_object(self, **kwargs):
            return timed_call('get_object', kwargs) if boundary == 'template-read' else upstream.get_object(**kwargs)

        def put_object(self, **kwargs):
            return timed_call('put_object', kwargs) if boundary == 'upload-response' else upstream.put_object(**kwargs)

    state.client = Client()
    try:
        yield state
    finally:
        release.set()
        server.shutdown()
        server.server_close()
        serving.join(3)
        stalled.close()
        assert not serving.is_alive(), 'owned timeout server did not stop'
