"""Create the narrowly corrected v2 snapshot without rewriting historical v1."""
import hashlib
import json
from pathlib import Path
from scoring import ROOT, load_dataset
from audit_references import POLICIES, LAB_REPLACEMENT


def build(root=ROOT):
    manifest, splits = load_dataset(root)
    if manifest['version'] != 'synthetic-v1':
        raise ValueError('Correction requires the original v1 snapshot')
    destination = root / 'datasets' / 'synthetic-v2'
    destination.mkdir(parents=True, exist_ok=False)
    old = POLICIES['lab'].encode()
    data = (root / 'heldout.jsonl').read_bytes()
    if data.count(old) != 8:
        raise ValueError('Expected exactly eight original laboratory passages')
    changed = [case['id'] for case in splits['heldout']
               if any(p['text'] == POLICIES['lab'] for p in case['policyPassages'])]
    manifest.update(version='synthetic-v2', annotationStatus='awaiting-versioned-review',
                    parentVersion='synthetic-v1', changedCaseIds=changed,
                    correction='Clarify laboratory cost-center requirement; no reference answers or quote facts change.',
                    decision='docs/adr/0006-ai-assisted-evaluation-review.md')
    for split in ('development', 'heldout'):
        name = split + '.jsonl'
        content = (root / name).read_bytes()
        if split == 'heldout':
            content = content.replace(old, LAB_REPLACEMENT.encode())
        (destination / name).write_bytes(content)
        manifest['files'][name]['sha256'] = hashlib.sha256(content).hexdigest()
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8', newline='\n')
    load_dataset(destination)
    return destination


if __name__ == '__main__':
    print(build())
