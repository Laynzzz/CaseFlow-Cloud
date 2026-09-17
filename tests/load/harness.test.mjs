import test from 'node:test';
import assert from 'node:assert/strict';
import {loadConfig, classifyIteration, summarizeJobs, parseHistogram} from './model.mjs';

test('load refuses external hosts and request counts beyond the bounded experiment', () => {
  assert.throws(()=>loadConfig({LOAD_API_URL:'https://example.com'}), /loopback/);
  assert.throws(()=>loadConfig({LOAD_RATE:'3'}), /LOAD_RATE/);
  assert.throws(()=>loadConfig({LOAD_DURATION_SECONDS:'9999'}), /LOAD_DURATION/);
  assert.throws(()=>loadConfig({LOAD_WARMUP_SECONDS:'-1'}), /LOAD_WARMUP/);
  assert.equal(loadConfig({}).offeredIterations,420);
});

test('deterministic mixed arrivals distribute reads and documents across both tenants', () => {
  const seen=Array.from({length:20},(_,i)=>classifyIteration(i));
  assert.equal(seen.filter(x=>x.kind==='document').length,4);
  assert.deepEqual(seen.filter(x=>x.kind==='document').map(x=>x.tenantIndex),[0,1,0,1]);
});

test('drain cannot claim completion when documents failed or approvals remain unresolved', () => {
  const r=summarizeJobs([{state:'SUCCEEDED',acknowledgedAt:100,observedAt:200,phase:'sustained'}, {state:'FAILED'}, {state:'APPROVED'}, {state:'CREATED'}]);
  assert.equal(r.completed,1); assert.equal(r.failed,1); assert.equal(r.pending,2);
  assert.equal(r.allCompleted,false); assert.equal(r.completionMs.p95,100);
});

test('histogram extraction keeps only requested kind and preserves cumulative buckets',()=>{
  const r=parseHistogram('worker_document_execution_seconds_bucket{kind="DOCUMENT",le="1.0"} 3\nworker_document_execution_seconds_bucket{kind="DOCUMENT",le="+Inf"} 4\nworker_document_execution_seconds_sum{kind="DOCUMENT"} 3.4\nworker_document_execution_seconds_count{kind="DOCUMENT"} 4\nworker_document_execution_seconds_count{kind="REVIEW"} 99','worker_document_execution_seconds','DOCUMENT');
  assert.deepEqual(r,{buckets:{'1.0':3,'+Inf':4},sum:3.4,count:4});
});

test('execution histogram aggregates success and failure bucket counts without overwriting',()=>{
  const raw='execution_bucket{kind="DOCUMENT",outcome="succeeded",le="1"} 3\nexecution_bucket{kind="DOCUMENT",outcome="failed",le="1"} 2\n';
  assert.equal(parseHistogram(raw,'execution','DOCUMENT').buckets['1'],5);
});
