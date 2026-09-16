import test from 'node:test';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {readFileSync} from 'node:fs';
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

test('AI reference review cannot masquerade as human verification',()=>{
  const review={status:'verified',datasetVersion:manifest.version,reviewer:'Codex AI assistant',
    reviewedAt:'2026-09-15',method:'ai-reference-review-v1',files:structuredClone(manifest.files)};
  for(const file of Object.values(review.files))file.reviewedCount=file.count;
  assert.throws(()=>requireAnnotationReview(manifest,review),/human reference review/);
});

test('AI learning profile requires exact complete resolved judgments',()=>{
  const dataset=loadFrozenDataset(fileURLToPath(new URL('.',import.meta.url)),'synthetic-v2');
  const review=JSON.parse(readFileSync(new URL('../docs/evidence/2026-09-15-r2/ai-reference-review-v2/audit.json',import.meta.url),'utf8'));
  const check=value=>requireAnnotationReview(dataset.manifest,value,'ai-reviewed-learning',dataset.splits);
  check(review);
  assert.throws(()=>requireAnnotationReview(dataset.manifest,review),/human reference review/);
  for(const alter of [
    value=>value.reviews.pop(),
    value=>value.reviews.push(value.reviews[0]),
    value=>value.reviews[0].issues.push({code:'UNRESOLVED'}),
    value=>value.reviews[0].caseSha256='stale',
    value=>value.reviews[0].fieldChecks.vendor=false,
    value=>value.files['heldout.jsonl'].sha256='stale',
    value=>value.files['heldout.jsonl'].reviewedCount=59,
    value=>value.humanVerified=true,
    value=>value.status='ai-reviewed-with-clarifications',
  ]) {
    const invalid=structuredClone(review);alter(invalid);
    assert.throws(()=>check(invalid));
  }
  assert.throws(()=>check(null));
  assert.throws(()=>loadFrozenDataset(fileURLToPath(new URL('.',import.meta.url)),'../synthetic-v2'));
});
