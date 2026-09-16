# Interrupted first held-out attempt

The manifest selected all 60 synthetic-v2 held-out cases before execution.
Five completed both jobs. Extraction for audio-006 failed, and the runner stopped
before its review and all later cases. The offline report retains the whole
preselected denominator: 19/240 extraction fields and 55 missing review outputs.
Those are incomplete-run scores, not a five-case success rate or completed quality
evaluation.

The durable call ledger records PROVIDER_PROCESS_ERROR after 10,438 ms. It has no
returned usage and retains its full USD 0.019661 reservation as UNKNOWN. The code
collapses several child/SDK failures into that safe category; the historical
record does not establish the lower-level cause. There was no prompt, schema,
retrieval or transport change to conceal or fix this unknown cause.

The distinct `heldout-v5-retry` directory records one unchanged complete rerun.
Do not merge its successes into this attempt or erase the earlier reservation.
Successful retry of audio-006 establishes recoverability in that attempt, not a
diagnosis of the original error. This run's accounted cost is USD 0.026477 including
the unknown reservation. The global USD 10 lifetime limit remains unchanged.

Raw predictions, all 16 provider ledger rows, 11 job timings, and derived reports
are retained alongside this note. The repeat subset was separately declared in
`../heldout-repeat-plan.json` before its additional calls.
