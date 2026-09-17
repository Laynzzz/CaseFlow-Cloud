"""A combined line score must not disguise missing critical branches."""
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location('ci_coverage', Path(__file__).parents[2] / 'scripts/ci-coverage.py')
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


def test_branch_gate_does_not_use_combined_line_percentage(tmp_path):
    java = tmp_path / 'java.xml'
    java.write_text('<report><package><class name="critical"><counter type="BRANCH" covered="8" missed="2"/></class></package></report>')
    python = tmp_path / 'python.json'
    python.write_text(json.dumps({'files': {'critical.py': {'summary': {
        'percent_covered': 99.99, 'covered_branches': 3, 'num_branches': 4}}}}))
    result = report.summarize(java, python, {'java': ['critical'], 'python': ['critical.py'],
                                          'minimum_branch_percent': 80, 'limitations': 'test'})
    assert result['modules'][0]['meets_target']
    assert result['modules'][1]['percent'] == 75
    assert not result['meets_target']
