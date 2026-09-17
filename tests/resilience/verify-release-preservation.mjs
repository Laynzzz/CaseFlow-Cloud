import assert from 'node:assert/strict';
import {readFileSync,readdirSync,writeFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {sessions} from '../load/oidc.mjs';

const values=Object.fromEntries(readFileSync('infrastructure/release/generated/.env','utf8').trim().split(/\r?\n/).map(line=>line.split('=')));
const fixture=JSON.parse(readFileSync('infrastructure/release/generated/release-ids.json','utf8'));
const auth=sessions({issuer:'http://127.0.0.1:18180/realms/caseflow',redirectUri:'http://127.0.0.1:18080/',password:values.DEMO_PASSWORD});
const token=await auth.token('requester');
async function api(path,method='GET') {
  const response=await fetch('http://127.0.0.1:18080/api/v1'+path,{method,headers:{Authorization:`Bearer ${token}`},signal:AbortSignal.timeout(10000)});
  assert.equal(response.status,200);return response.json();
}
const verified=[];
for(const entry of readdirSync('output/r3-release-recovery',{withFileTypes:true})) {
  if(!entry.isDirectory())continue;
  let original;
  try{original=JSON.parse(readFileSync(`output/r3-release-recovery/${entry.name}/result.json`,'utf8'));}catch{continue;}
  if(!original.passed)continue;
  const path=`/tenants/${fixture.tenantId}/cases/${original.caseId}`;
  const item=await api(path);assert.equal(item.state,'APPROVED');assert.equal(item.documentStatus,'SUCCEEDED');
  const job=await api(`/tenants/${fixture.tenantId}/jobs/${original.jobId}`);assert.equal(job.sha256,original.sha256);
  const download=await api(`${path}/documents/${original.jobId}/download-url`,'POST');
  assert.equal(new URL(download.url).origin,'http://127.0.0.1:18333');
  const response=await fetch(download.url,{signal:AbortSignal.timeout(10000)});assert.equal(response.status,200);
  const bytes=Buffer.from(await response.arrayBuffer());assert.equal(createHash('sha256').update(bytes).digest('hex'),original.sha256);
  const audit=await api(path+'/audit');assert.equal(audit.items.filter(e=>e.eventType==='DOCUMENT_SUCCEEDED').length,1);
  verified.push({caseId:original.caseId,jobId:original.jobId,sha256:original.sha256,bytes:bytes.length,completionAudits:1});
}
assert.ok(verified.length>=2,'Need both dependency-recovery documents before rollback preservation proof');
const label=process.argv[2]??'rollback';assert.match(label,/^[a-z-]+$/);
writeFileSync(`output/r3-release/${label}-preservation.json`,JSON.stringify({at:new Date().toISOString(),verified},null,2)+'\n');
console.log(`PASS ${verified.length} pre-existing fault-recovery documents preserve state, checksum, bytes and single completion audit`);
