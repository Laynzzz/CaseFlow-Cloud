import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {client,signIn} from './oidc-session.mjs';
const fixture=JSON.parse(readFileSync(new URL('../../infrastructure/local/generated/demo-ids.json',import.meta.url)));
const adminToken=await signIn('admin'),requesterToken=await signIn('requester');
const admin=client(adminToken),requester=client(requesterToken),outsider=client(await signIn('outsider'));
const tenant=`/tenants/${fixture.acmeId}`,path=tenant+'/sources';
const bytes=Buffer.from('Equipment purchases require a cost center before approval.\nSynthetic policy for R2 testing.');
const body={name:'Synthetic equipment policy',kind:'POLICY',mediaType:'text/plain',byteSize:bytes.length};
await requester(path,{method:'POST',body,expected:403});
let policy=await admin(path,{method:'POST',body});
await outsider(`${path}/${policy.id}`,{expected:404});
await requester(`${path}/${policy.id}`,{expected:404});
await admin(`${path}/${policy.id}/publish`,{method:'POST',body:{expectedVersion:0},expected:400});
async function upload(id,content,token=adminToken,expected=200) {
  const response=await fetch(`http://127.0.0.1:8080/api/v1${path}/${id}/content`,{method:'PUT',headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/octet-stream'},body:content});
  assert.equal(response.status,expected,await response.text());
}
async function indexed(actor,id,expected='INDEXED') {
  let source;
  for(let n=0;n<80;n++) {
    source=await actor(`${path}/${id}`);
    if(source.state===expected) return source;
    assert.notEqual(source.state,'FAILED',`Unexpected failure: ${source.failureCode}`);
    await new Promise(resolve=>setTimeout(resolve,750));
  }
  assert.fail(`Source did not reach ${expected}; state=${source?.state}`);
}
await upload(policy.id,Buffer.from('mismatch'),adminToken,400);
await upload(policy.id,bytes);
const key=crypto.randomUUID();
policy=await admin(`${path}/${policy.id}/finalize`,{method:'POST',key,body:{expectedVersion:0}});
assert.equal(policy.state,'INDEXING');
assert.deepEqual(await admin(`${path}/${policy.id}/finalize`,{method:'POST',key,body:{expectedVersion:0}}),policy);
await upload(policy.id,bytes,adminToken,400);
policy=await indexed(admin,policy.id);
const chunks=await admin(`${path}/${policy.id}/chunks`);
assert.equal(chunks.items[0].text,bytes.toString());
assert.equal(chunks.metadata.pageCount,1);
policy=await admin(`${path}/${policy.id}/publish`,{method:'POST',body:{expectedVersion:policy.version}});
assert.equal(policy.state,'PUBLISHED');
assert.equal((await requester(`${path}/${policy.id}/chunks`)).items[0].text,bytes.toString());
await outsider(`${path}/${policy.id}/chunks`,{expected:404});
console.log('PASS policy upload, immutable bytes, idempotency, asynchronous text index, publication and tenant isolation');

const purchase={vendor:'Synthetic quote vendor',description:'Equipment',currency:'USD',costCenter:'',justification:'Synthetic R2 check',lineItems:[{description:'Equipment',quantity:'2',unitPrice:'2100'}]};
let draft=await requester(tenant+'/cases',{method:'POST',body:{purchase}});
const quoteBytes=Buffer.from('Vendor: Synthetic quote vendor\n2 Equipment at USD 2100 each\nTotal USD 4200');
const quote=await requester(path,{method:'POST',body:{name:'Synthetic quote',kind:'QUOTE',caseId:draft.id,expectedCaseVersion:draft.version,mediaType:'text/plain',byteSize:quoteBytes.length}});
await upload(quote.id,quoteBytes,adminToken,403);
await upload(quote.id,quoteBytes,requesterToken);
await requester(`${path}/${quote.id}/finalize`,{method:'POST',body:{expectedVersion:0,expectedCaseVersion:draft.version+1},expected:409});
await requester(`${path}/${quote.id}/finalize`,{method:'POST',body:{expectedVersion:0,expectedCaseVersion:draft.version}});
await indexed(requester,quote.id);
const changed=await requester(`${tenant}/cases/${draft.id}`);
assert.equal(changed.version,draft.version+1);assert.deepEqual(changed.purchase,draft.purchase);
await outsider(`${path}?caseId=${draft.id}`,{expected:404});
assert.equal((await requester(`${path}/${quote.id}/chunks`)).items[0].text,quoteBytes.toString());
console.log('PASS quote owner permissions, stale draft protection, revision bump, unchanged manual purchase data');

const pins=await requester(`${tenant}/cases/${draft.id}/policies/refresh`,{method:'POST',body:{expectedVersion:changed.version}});
assert.ok(pins.items.some(p=>p.id===policy.id));
const search=await requester(`${tenant}/cases/${draft.id}/policies/search?query=cost%20center`);
assert.ok(search.items.some(p=>p.sourceId===policy.id));
await outsider(`${tenant}/cases/${draft.id}/policies/search?query=cost`,{expected:404});
let started=await requester(`${tenant}/cases/${draft.id}`);
started=await requester(`${tenant}/cases/${draft.id}`,{method:'PUT',body:{purchase:{...purchase,costCenter:'OPS-TEST'},workflowId:fixture.workflowId,templateId:fixture.templateId,expectedVersion:started.version}});
started=await requester(`${tenant}/cases/${draft.id}/assignments`,{method:'PUT',body:{expectedVersion:started.version,approverIds:[fixture.users.manager,fixture.users.finance]}});
started=await requester(`${tenant}/cases/${draft.id}/start`,{method:'POST',body:{expectedVersion:started.version}});
await requester(`${tenant}/cases/${draft.id}/policies/refresh`,{method:'POST',body:{expectedVersion:started.version},expected:409});

const invalid=Buffer.from('%PDF-not-a-valid-file');
const bad=await admin(path,{method:'POST',body:{...body,name:'Synthetic malformed PDF',mediaType:'application/pdf',byteSize:invalid.length}});
await upload(bad.id,invalid);
await admin(`${path}/${bad.id}/finalize`,{method:'POST',body:{expectedVersion:0}});
const failed=await indexed(admin,bad.id,'FAILED');
assert.equal(failed.failureCode,'MALFORMED_PDF');
await admin(`${path}/${bad.id}/publish`,{method:'POST',body:{expectedVersion:failed.version},expected:400});
policy=await admin(`${path}/${policy.id}/deactivate`,{method:'POST',body:{expectedVersion:policy.version}});
assert.equal(policy.state,'DEACTIVATED');
assert.ok(!(await requester(path)).items.some(s=>s.id===policy.id));
assert.equal((await requester(`${path}/${policy.id}/chunks?caseId=${draft.id}`)).items[0].text,bytes.toString());
await requester(`${path}/${policy.id}/chunks`,{expected:404});
assert.ok((await requester(`${tenant}/cases/${draft.id}/policies/search?query=cost%20center`)).items.some(p=>p.sourceId===policy.id));
console.log('PASS clear malformed-file failure, failed-policy publication blocked, deactivated policy excluded');
console.log('PASS policy refresh, scoped full-text retrieval, started pin immutability, historical deactivated-policy access');
const assistant=await requester(`${tenant}/cases/${draft.id}/assistant`);
if(!assistant.enabled) {
  const before=assistant.items.length;
  await requester(`${tenant}/cases/${draft.id}/assistant`,{method:'POST',body:{kind:'REVIEW',expectedVersion:started.version},expected:503});
  assert.equal((await requester(`${tenant}/cases/${draft.id}/assistant`)).items.length,before);
  console.log('PASS disabled AI budget rejects job admission; manual source and policy workflows remain available');
}
await outsider(`${tenant}/cases/${draft.id}/assistant`,{expected:404});
