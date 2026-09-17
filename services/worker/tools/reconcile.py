"""Trusted-host CLI; exit 0=no findings, 2=findings, 1=report failed."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from caseflow_worker.reconciliation import reconcile


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--age-seconds', type=int, default=300)
    parser.add_argument('--limit', type=int, default=100)
    args = parser.parse_args(argv)
    try:
        report = reconcile(age_seconds=args.age_seconds, limit=args.limit)
    except Exception as error:
        # Driver messages can contain DSNs or business data; keep stdout structured.
        print(json.dumps({'status': 'REPORT_FAILED', 'errorType': type(error).__name__}))
        return 1
    print(json.dumps(report, indent=2))
    return 2 if report['findings'] else 0


if __name__ == '__main__':
    sys.exit(main())
