# ADR 0005: enforce provider deadlines from the worker parent

Date: 2026-09-15. Status: implemented; live compatibility verification pending.

A socket read timeout can restart as bytes arrive. It is insufficient to enforce
the plan's elapsed-time limit for an AI call. A disposable Python child now owns
each generation or embedding request. The worker parent kills and waits for it
after 30 seconds, including child startup and response serialization. The SDK
also has a 20-second network timeout and no automatic retries.

The parent retains database admission, authorization, accounting and result
selection. The child receives only the provider request on stdin and a restricted
environment with the provider key, runtime paths and network certificate/proxy
configuration. It receives no database or object-storage credentials. Its only
operations are generation and embeddings at the fixed provider URL. Stdout is a
bounded structured result; stderr and exception bodies are not recorded.

Use the existing parser resource-limit mechanism: 512 MiB address/process memory;
Windows also limits active processes to one, while POSIX caps CPU time at 15
seconds. These are resource limits, not a filesystem or network sandbox. Inherited
user filesystem permissions still apply. Windows child creation is hidden.

A deadline or lost response may still have incurred a provider charge. Keep the
ledger reservation UNKNOWN instead of refunding it or retrying invisibly. Any
later authorized retry must obtain a fresh reservation. Successful usage settles
normally, and revoked or stale results still cannot become selected business data.

Trade-offs: interpreter/SDK startup adds latency and cannot reuse HTTP connections.
A late valid answer is discarded, potentially after it was billed. The deadline
is per provider call; a comparison review can make one embedding call plus one
generation call, with separate bounded database work. This is not an end-to-end
30-second job SLA. Operating-system process creation/termination and host sleep
can delay return; test the supported host and do not claim a real-time guarantee.

Evidence: `services/worker/tests/test_provider_transport.py` kills a real sleeping
child and verifies it cannot write afterward, checks credential exclusion and
rejects malformed output. `test_ai_provider.py` verifies that a parent deadline
creates one UNKNOWN charge with the reserved amount retained.
