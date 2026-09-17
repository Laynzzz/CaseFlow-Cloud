import importlib.util
import pytest
from pathlib import Path

spec = importlib.util.spec_from_file_location('scan_review', Path('scripts/scan-review.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture():
    finding = {'VulnerabilityID': 'CVE-2026-54369', 'PkgName': 'libacl1',
               'InstalledVersion': '2.3.2-2+b1', 'Severity': 'HIGH'}
    exception = {'id': finding['VulnerabilityID'], 'packages': {'libacl1': '2.3.2-2+b1'},
                 'expires': '2026-10-01', 'reason': 'No privileged pathname ACL operations'}
    report = {'Metadata': {'OS': {'Family': 'debian', 'Name': '13.7'}},
              'Results': [{'Class': 'os-pkgs', 'Vulnerabilities': [finding]}]}
    return report, finding, {'exceptions': [exception]}


def test_only_exact_unfixed_reviewed_worker_finding_is_accepted():
    report, _, policy = fixture()
    result = module.review(report, policy, 'worker', '2026-09-17')
    assert len(result['accepted']) == 1
    assert result['blocking'] == []


def test_changed_scope_fix_severity_version_and_expiry_fail_closed():
    for change in ('image', 'fix', 'critical', 'version', 'expiry', 'distro', 'library', 'unknown'):
        report, finding, policy = fixture()
        image, date = 'worker', '2026-09-17'
        if change == 'image': image = 'api'
        if change == 'fix': finding['FixedVersion'] = '2.4.0'
        if change == 'critical': finding['Severity'] = 'CRITICAL'
        if change == 'version': finding['InstalledVersion'] = '2.3.3'
        if change == 'expiry': date = '2026-10-01'
        if change == 'distro': report['Metadata']['OS']['Name'] = '12.9'
        if change == 'library': report['Results'][0]['Class'] = 'lang-pkgs'
        if change == 'unknown': finding['VulnerabilityID'] = 'CVE-2099-12345'
        result = module.review(report, policy, image, date)
        assert len(result['blocking']) == 1, change
        assert result['accepted'] == [], change


def test_missing_report_data_is_not_a_clean_scan():
    with pytest.raises(ValueError):
        module.review({}, {'exceptions': []}, 'worker', '2026-09-17')
