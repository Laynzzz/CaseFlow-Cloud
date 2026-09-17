import test from 'node:test';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {loadFrozenDataset, requireAnnotationReview} from './dataset.mjs';
const root = fileURLToPath(new URL('.', import.meta.url));

test('v3 retires all v2 cases unchanged and loads 60 disjoint fresh heldout cases', () => {
  const previous = loadFrozenDataset(root, 'synthetic-v2');
  const {manifest, splits} = loadFrozenDataset(root, 'synthetic-v3');
  assert.deepEqual(splits.development, [...previous.splits.development, ...previous.splits.heldout]);
  assert.equal(splits.development.length, 120);
  assert.equal(splits.heldout.length, 60);
  assert.equal(new Set(splits.heldout.map(c => c.family)).size, 6);
  assert.equal(manifest.annotationStatus, 'awaiting-versioned-review');
  assert.deepEqual(manifest.targets, {extraction: .90, recallAt5: .90, claimSupport: .95});
  assert.throws(() => requireAnnotationReview(manifest, null, 'ai-reviewed-learning', splits));
});

test('all three supported versions load without changing the default or allowing arbitrary paths', () => {
  assert.equal(loadFrozenDataset(root).manifest.version, 'synthetic-v1');
  for (const version of ['synthetic-v1', 'synthetic-v2', 'synthetic-v3']) {
    assert.equal(loadFrozenDataset(root, version).manifest.version, version);
  }
  for (const version of ['synthetic-v4', '../synthetic-v3']) {
    assert.throws(() => loadFrozenDataset(root, version), /Unknown frozen dataset version/);
  }
});
