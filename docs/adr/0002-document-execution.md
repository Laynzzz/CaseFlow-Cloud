# ADR 0002: document execution and local object storage

Status: accepted design; implementation/verification in progress, September 14.

## Decision

Preserve the plan's Java outbox -> Kafka -> Python worker -> worker completion
outbox -> Kafka -> Java structure. Use Apache Kafka 4.2.1 and SeaweedFS 4.47 for
local S3-compatible storage, pinned to verified Linux amd64 image digests.
The AWS profile will use S3. One local broker has no high availability; loopback
PLAINTEXT is a local-only configuration. Cloud needs private networking and its
own security configuration. Kafka is required by the plan; a SQL-only queue
would otherwise be simpler for this workload.

SeaweedFS is an implementation choice within the plan's local-storage adapter.
Use only a tested subset of the S3 API, not an assumption of full compatibility.
Local generated credentials stay in ignored .env. Only port 8333 is published;
other storage administration surfaces remain inside Docker networking.
These containers and volumes are development infrastructure, not AWS evidence.

Uploaded templates will permit plain allowlisted placeholders, not arbitrary
Jinja expressions. Validate compressed and expanded sizes, XML, relationships
and placeholder syntax; copy the exact validated bytes to an immutable object
key. Starting pins a published template. A document job receives that template
reference plus an immutable approved input snapshot. Its output is written to
an attempt/fencing-specific key and selected only by a successful fenced update.

The worker owns worker tables, while Java owns core state. Narrow SQL views
expose immutable job inputs and authorized results across this boundary. No
Python update may approve a case. Generation failure leaves approval intact.

## Trade-offs and gates

More moving parts than synchronous rendering; in exchange, request transactions
stay short and work can recover after a process restart. At-least-once delivery
can repeat events, object writes and execution. Stable IDs, receipts and fencing
protect business effects; they do not create exactly-once transport.

R1 still requires real template upload/download, duplicate scheduling, lease
recovery, stale-worker rejection, completion replay and cloud smoke evidence.
No completion gate is claimed by adding these containers.

Sources checked during selection: [Apache Kafka Docker](https://kafka.apache.org/42/getting-started/docker/),
[SeaweedFS quick start](https://github.com/seaweedfs/seaweedfs),
[AWS SDK presigning](https://docs.aws.amazon.com/sdk-for-java/latest/developer-guide/examples-s3-presign.html),
[docxtpl escaping](https://docxtpl.readthedocs.io/en/stable/).
