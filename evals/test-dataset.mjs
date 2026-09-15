import test from 'node:test';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {loadFrozenDataset,requireAnnotationReview} from './dataset.mjs';
const {manifest,splits}=loadFrozenDataset(fileURLToPath(new URL('.',import.meta.url)));
test('frozen datasets contain 120 cases and disjoint families',()=>{
  assert.equal(splits.development.length,60);assert.equal(splits.heldout.length,60);
  const families=new Set(splits.development.map(r=>r.family));
  assert.ok(splits.heldout.every(r=>!families.has(r.family)));
});
test('held-out run refuses absent, partial or stale human reference review',()=>{
  assert.throws(()=>requireAnnotationReview(manifest,null),/human reference review/);
  const review={status:'verified',datasetVersion:manifest.version,reviewer:'Synthetic test fixture',
    reviewedAt:'2026-09-15',method:'human-reference-review',files:structuredClone(manifest.files)};
  assert.throws(()=>requireAnnotationReview(manifest,review),/all rows/);
  for(const file of Object.values(review.files)) file.reviewedCount=file.count;
  requireAnnotationReview(manifest,review);
  review.files['heldout.jsonl'].sha256='wrong';
  assert.throws(()=>requireAnnotationReview(manifest,review),/exact frozen/);
});
