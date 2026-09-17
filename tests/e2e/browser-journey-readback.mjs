// Read back a synthetic browser-created purchase; performs no business mutations.
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync} from 'node:fs';
import {parseArgs} from 'node:util';
import {createHash} from 'node:crypto';
import {signIn,client} from './oidc-session.mjs';
const {values}=parseArgs({options:{tenant:{type:'string'},case:{type:'string'},document:{type:'string'},output:{type:'string'}}});
for(const key of ['tenant','case','document','output']) assert.ok(values[key],`Missing --${key}`);
const actor=client(await signIn('requester'));
const path=`/tenants/${values.tenant}/cases/${values.case}`;
const purchase=await actor(path), audit=await actor(path+'/audit'), jobs=await actor(path+'/assistant'), documents=await actor(path+'/documents');
assert.equal(purchase.state,'APPROVED');
assert.equal(purchase.purchase.total,'70.00');
assert.equal(purchase.purchase.vendor,'Synthetic Browser Supplies 12');
assert.equal(purchase.purchase.costCenter,'OPS-BROWSER-R2');
assert.deepEqual(purchase.assignments.map(row=>row.displayName),['manager','finance']);
assert.ok(purchase.assignments.every(row=>row.outcome==='APPROVED'));
assert.equal(audit.items.filter(row=>row.eventType==='CASE_APPROVE').length,2);
assert.ok(audit.items.some(row=>row.eventType==='AI_SUGGESTIONS_ACCEPTED'));
const extraction=jobs.items.find(row=>row.kind==='EXTRACTION'), review=jobs.items.find(row=>row.kind==='REVIEW');
assert.equal(extraction.status,'SUCCEEDED'); assert.equal(review.status,'SUCCEEDED');
assert.equal(extraction.stale,true); assert.equal(review.stale,true);
const bytes=readFileSync(values.document),sha256=createHash('sha256').update(bytes).digest('hex');
assert.equal(documents.items.length,1);
assert.equal(documents.items[0].status,'SUCCEEDED');
assert.equal(documents.items[0].sha256,sha256);
assert.equal(documents.items[0].byteSize,bytes.length);
writeFileSync(values.output,JSON.stringify({observedAt:new Date().toISOString(),synthetic:true,
  method:'API readback after separate observed browser journey; not browser automation replay',
  tenantId:values.tenant,caseId:values.case,purchase,audit,extraction,review,documents,
  downloadedDocument:{sha256,byteSize:bytes.length},checksPassed:true},null,2)+'\n',{flag:'wx'});
console.log('PASS browser purchase readback, ordered approvals, accepted suggestions and downloaded-byte identity');
