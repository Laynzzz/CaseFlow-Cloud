"""Report actual per-module BRANCH coverage; never substitute combined line coverage."""
from pathlib import Path
import argparse
import json
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def summarize(java_xml, python_json, scope):
    rows = []
    classes = {item.attrib['name']: item for item in ET.parse(java_xml).findall('.//class')}
    python = json.loads(Path(python_json).read_text())['files']
    python = {name.replace('\\', '/'): value for name, value in python.items()}
    for name in scope['java']:
        if name not in classes:
            raise ValueError('Declared Java module absent from coverage report: ' + name)
        counter = classes[name].find("counter[@type='BRANCH']")
        if counter is None:
            raise ValueError('Declared Java module has no branch counter: ' + name)
        covered, missed = int(counter.attrib['covered']), int(counter.attrib['missed'])
        rows.append(dict(language='java', module=name, covered=covered, total=covered + missed))
    for name in scope['python']:
        matches = [data for path, data in python.items() if path == name or path.endswith('/' + name)]
        if len(matches) != 1:
            raise ValueError('Declared Python module missing or ambiguous: ' + name)
        summary = matches[0]['summary']
        rows.append(dict(language='python', module=name, covered=summary['covered_branches'], total=summary['num_branches']))
    for row in rows:
        if row['total'] == 0:
            raise ValueError('Declared module has no measured branches: ' + row['module'])
        row['percent'] = round(100 * row['covered'] / row['total'], 2)
        row['meets_target'] = 100 * row['covered'] >= scope['minimum_branch_percent'] * row['total']
    return dict(minimum_branch_percent=scope['minimum_branch_percent'], modules=rows,
                meets_target=all(row['meets_target'] for row in rows), limitations=scope['limitations'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--java', type=Path, required=True)
    parser.add_argument('--python', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = summarize(args.java, args.python, json.loads((ROOT / 'tests/ci/coverage-scope.json').read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    raise SystemExit(0 if result['meets_target'] else 1)
