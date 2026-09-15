// Opt-in paid synthetic integration check. All calls use the worker's shared spend ledger.
import assert from 'node:assert/strict';
import {readFileSync, mkdirSync, writeFileSync} from 'node:fs';
import {client, signIn} from './oidc-session.mjs';

if (!process.argv.includes('--live')) throw new Error('Requires --live and a configured, authorized AI budget');
const fixture = JSON.parse(readFileSync(new URL('../../infrastructure/local/generated/demo-ids.json', import.meta.url)));
const token = await signIn('requester'), adminToken = await signIn('admin');
const requester = client(token), admin = client(adminToken);
const tenant = `/tenants/${fixture.acmeId}`;
const run = {startedAt: new Date().toISOString(), tenantId: fixture.acmeId, checks: []};
const directory = new URL(`../../docs/evidence/2026-09-15-r2/live-${Date.now()}/`, import.meta.url);
mkdirSync(directory, {recursive: true});
const save = () => writeFileSync(new URL('journey.json', directory), JSON.stringify(run, null, 2)+'\n');
async function source(actor, bearer, kind, text, draft) {
  const bytes = Buffer.from(text);
  let value = await actor(tenant+'/sources', {method:'POST', body:{name:`Synthetic live ${kind.toLowerCase()}`, kind, mediaType:'text/plain', byteSize:bytes.length,
    ...(draft ? {caseId:draft.id, expectedCaseVersion:draft.version} : {})}});
  const path = `${tenant}/sources/${value.id}`;
  const response = await fetch(`http://127.0.0.1:8080/api/v1${path}/content`, {method:'PUT', headers:{Authorization:`Bearer ${bearer}`, 'Content-Type':'application/octet-stream'}, body:bytes});
  assert.equal(response.status, 200);
  await actor(path+'/finalize', {method:'POST', body:{expectedVersion:0, ...(draft ? {expectedCaseVersion:draft.version} : {})}});
  for (let i=0; i<80; i++) {
    value = await actor(path);
    if (value.state==='INDEXED') return value;
    assert.notEqual(value.state, 'FAILED', value.failureCode);
    await new Promise(resolve=>setTimeout(resolve,750));
  }
  throw new Error('Source indexing timed out');
}
async function completed(path, requested) {
  for (let i=0; i<100; i++) {
    const job = (await requester(path)).items.find(item=>item.jobId===requested.jobId);
    if (job && ['SUCCEEDED','FAILED'].includes(job.status)) return job;
    await new Promise(resolve=>setTimeout(resolve,750));
  }
  throw new Error('Assistant job timed out');
}
try {
  const purchase = {vendor:'', description:'Equipment purchase', currency:'USD', costCenter:'', justification:'Synthetic equipment replacement', lineItems:[]};
  let draft = await requester(tenant+'/cases', {method:'POST', body:{purchase}});
  run.caseId = draft.id; save();
  let policy = await source(admin, adminToken, 'POLICY', 'Equipment purchases require a cost center before approval. This is a synthetic purchasing policy.');
  policy = await admin(`${tenant}/sources/${policy.id}/publish`, {method:'POST', body:{expectedVersion:policy.version}});
  run.policy = policy;
  run.quote = await source(requester, token, 'QUOTE', 'Vendor: Synthetic Equipment Ltd\nCurrency: USD\nItem: Equipment; Quantity: 2; Unit price: 2100.00\nTotal: 4200.00 USD', draft);
  draft = await requester(`${tenant}/cases/${draft.id}`);
  await requester(`${tenant}/cases/${draft.id}/policies/refresh`, {method:'POST', body:{expectedVersion:draft.version}});
  draft = await requester(`${tenant}/cases/${draft.id}`);
  const path = `${tenant}/cases/${draft.id}/assistant`;
  const request = {kind:'EXTRACTION', expectedVersion:draft.version, sourceId:run.quote.id};
  const job = await requester(path, {method:'POST', body:request});
  assert.equal((await requester(path, {method:'POST', body:request})).jobId, job.jobId);
  run.extraction = await completed(path, job); save();
  assert.equal(run.extraction.status, 'SUCCEEDED', run.extraction.failureCode);
  assert.deepEqual((await requester(`${tenant}/cases/${draft.id}`)).purchase, draft.purchase);
  const proposed = run.extraction.result.output;
  assert.equal(proposed.vendor.value, 'Synthetic Equipment Ltd');
  assert.equal(Number(proposed.total.value), 4200);
  const key = crypto.randomUUID(), accept = {expectedVersion:draft.version, fields:['vendor','currency','lineItems']};
  run.acceptance = await requester(`${path}/${job.jobId}/accept`, {method:'POST', key, body:accept});
  assert.deepEqual(await requester(`${path}/${job.jobId}/accept`, {method:'POST', key, body:accept}), run.acceptance);
  draft = await requester(`${tenant}/cases/${draft.id}`);
  assert.equal(draft.purchase.vendor, proposed.vendor.value);
  assert.equal(Number(draft.purchase.total),4200);
  assert.equal(draft.purchase.justification, purchase.justification);
  run.checks.push('Live extraction; no automatic mutation; selected acceptance; replay; preserved manual justification');
  console.log('PASS live extraction and explicit suggestion acceptance');
  const review = await requester(path, {method:'POST', body:{kind:'REVIEW', expectedVersion:draft.version}});
  run.review = await completed(path,review); save();
  assert.equal(run.review.status,'SUCCEEDED',run.review.failureCode);
  assert.ok(run.review.result.output.policy_findings.length>0);
  assert.ok(Object.values(run.review.result.evidence).some(chunk=>chunk.sourceId===policy.id));
  assert.deepEqual((await requester(`${tenant}/cases/${draft.id}`)).purchase, draft.purchase);
  run.checks.push('Live cited review; relevant pinned policy retrieved; review does not change purchase');
  run.completedAt = new Date().toISOString(); save();
  console.log('PASS live policy review; case '+draft.id);
  console.log('Evidence: '+directory.pathname);
} catch (error) {
  run.failure = error.message; save(); throw error;
}
