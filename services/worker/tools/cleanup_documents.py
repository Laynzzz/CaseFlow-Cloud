"""Preview one succeeded document job's old unselected objects; explicit apply only.

Apply requires a NEW JSONL report file. A pending intent or truncated last line
means the outcome is unknown; inspect storage and durable job state before retry.
This trusted-host operator tool uses worker credentials, never tenant credentials.
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from caseflow_worker.cleanup import DeletionJournal, apply, preview


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tenant', required=True)
    parser.add_argument('--job', required=True)
    parser.add_argument('--grace-hours', type=float, default=24)
    parser.add_argument('--limit', type=int, default=100, help='maximum listed objects, 1..1000')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--report', type=Path, help='new append-only JSONL report; required with --apply')
    args = parser.parse_args(argv)
    if args.apply and args.report is None:
        parser.error('--apply requires --report with a new file path')
    if not args.apply and args.report is not None:
        parser.error('--report is for apply; redirect preview stdout to save JSON')
    try:
        report = preview(args.tenant, args.job, grace_hours=args.grace_hours, limit=args.limit)
        if not args.apply:
            print(json.dumps(report, indent=2))
            return 0
        with DeletionJournal(args.report, report) as journal:
            result = apply(report, journal)
        print(json.dumps(dict(report=str(args.report), **result)))
        return 1 if result['unknown'] or result['notAttempted'] else 0
    except (Exception, KeyboardInterrupt) as error:
        # Driver exception text can include credentials; only emit the type.
        print(f'Cleanup stopped ({type(error).__name__}); inspect any report for pending intents.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
