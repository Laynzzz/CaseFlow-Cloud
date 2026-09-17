"""Keep raw scanner findings; apply only expiring, exact worker OS reviews."""
import argparse
from datetime import date
import json
from pathlib import Path


def review(report, policy, image, today):
    if not isinstance(report.get('Results'), list) or not isinstance(report.get('Metadata'), dict):
        raise ValueError('Missing scanner results or image metadata')
    result = {'image': image, 'review_date': today, 'accepted': [], 'blocking': []}
    operating_system = report.get('Metadata', {}).get('OS', {})
    scope = (image == 'worker' and operating_system.get('Family') == 'debian'
             and operating_system.get('Name', '').split('.')[0] == '13')
    for group in report.get('Results', []):
        for item in group.get('Vulnerabilities', []):
            if item['Severity'] not in ('HIGH', 'CRITICAL'):
                continue
            match = next((rule for rule in policy['exceptions'] if
                          scope and group.get('Class') == 'os-pkgs'
                          and item['Severity'] == 'HIGH' and not item.get('FixedVersion')
                          and rule['id'] == item['VulnerabilityID']
                          and rule['packages'].get(item['PkgName']) == item['InstalledVersion']
                          and today < rule['expires']), None)
            entry = {key: item.get(key) for key in
                     ('VulnerabilityID', 'PkgName', 'InstalledVersion', 'FixedVersion', 'Severity')}
            if match:
                entry.update(reason=match['reason'], expires=match['expires'])
            result['accepted' if match else 'blocking'].append(entry)
    result['passed_with_reviewed_exceptions'] = not result['blocking']
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', required=True)
    parser.add_argument('--policy', default='tests/ci/vulnerability-reviews.json')
    parser.add_argument('--image', choices=('api', 'worker'), required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = review(json.loads(Path(args.report).read_text()),
                    json.loads(Path(args.policy).read_text()), args.image, date.today().isoformat())
    Path(args.output).write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(f"{args.image}: {len(result['blocking'])} blocking; {len(result['accepted'])} reviewed unfixed findings")
    raise SystemExit(1 if result['blocking'] else 0)
