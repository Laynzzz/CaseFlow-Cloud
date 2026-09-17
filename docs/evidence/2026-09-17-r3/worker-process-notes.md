# Worker process interruption evidence

Source checkpoint: `12d339a`. Fresh focused run: **9 passed in 15.29 seconds**,
zero failures/errors/skips. Five cases terminate real spawned Python processes;
four additional cases reject a demo/malformed database name or nonlocal endpoint.
Raw [output](worker-process.txt), [JUnit report](worker-process.xml), and
[negative control](worker-negative-control.txt) are retained.

The JUnit suite properties record each boundary, child PID, nonzero termination
exit code, UTC reached/terminated timestamps and relevant lease/result metadata.
Only the harness-owned child is terminated. The application and Vite health
smoke checks passed after this run.

## Observations

| Actual process termination | State after termination and recovery |
| --- | --- |
| Before scheduling commit | No job or inbox row; replay stores exactly one of each |
| After scheduling commit | QUEUED job and inbox survive; duplicate scheduling does not create another |
| Before result commit | RUNNING job survives, no artifact/success event; the real five-second lease expires, higher fence reclaims and selects one result |
| After result commit | SUCCEEDED job, one artifact and success event survive; replay, old finalization and late failure have no second effect |
| After object upload | Uploaded DOCX exists without selected artifact; real lease expires; a new immutable object is selected; the old owner is fenced and its object bytes remain unchanged |

The upload case reads the real local S3-compatible store, verifies the template
and both document checksums, and opens the selected DOCX to check the synthetic
vendor and USD 70.00 total. Cleanup deletes only that random fixture's template
and document keys. This demonstrates the orphan window; it does not implement
or verify production garbage collection.

Result-transaction cases use synthetic artifact metadata to isolate database
atomicity. The separate upload case exercises actual object storage/rendering.
The fixtures' immutable input/read views and actual worker-role SQL are used;
the parent does not shorten leases through SQL or alter the running demo.

## Probe sensitivity and limits

Initial test collection failed because the probe helper did not exist. After
implementing it, five crash scenarios passed. A temporary negative control then
replaced `Process.terminate()` with an IPC release, allowing normal exit. Both
scheduling cases failed specifically with **normal exit is not crash evidence**.
The mutation was restored before the recorded nine-test run.

The child calls real scheduling/result/rendering functions and pauses at a
test-only transaction wrapper or immediately after a real operation. It is not
the full long-running FastAPI dispatcher. Kafka offset/publisher crashes,
broker/database restarts, S3 timeouts and Java completion are not proven by these
Python tests. They have separate evidence or remain open in the R3 map.

Implementation uses Python's explicit `spawn` context and `Process.terminate`,
whose platform behavior is documented in the
[Python 3.12 multiprocessing reference](https://docs.python.org/3.12/library/multiprocessing.html).
Windows and Linux termination mechanisms differ; this recorded run is Windows.
