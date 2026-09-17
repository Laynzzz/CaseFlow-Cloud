// Explicit local release fault probe. Never targets the user's development project.
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {mkdirSync,readFileSync,writeFileSync} from 'node:fs';
import {randomUUID,createHash} from 'node:crypto';
import {sessions} from '../load/oidc.mjs';
import {ownedDependency} from './release-guards.mjs';

const service=process.argv[2];
assert.ok(['postgres','kafka'].includes(service),'Choose postgres or kafka');
const directory=`output/r3-release-recovery/${service}-${new Date().toISOString().replaceAll(':','-')}`;
mkdirSync(directory,{recursive:true});
const save=(name,data)=>writeFileSync(`${directory}/${name}`,JSON.stringify(data,null,2)+'\n');
const values=Object.fromEntries(readFileSync('infrastructure/release/generated/.env','utf8').trim().split(/\r?\n/).map(line=>line.split('=')));
const fixture=JSON.parse(readFileSync('infrastructure/release/generated/release-ids.json','utf8'));
const docker=(args)=>execFileSync('docker',args,{encoding:'utf8',stdio:['ignore','pipe','pipe']}).trim();
const found=docker(['ps','-q','--filter','label=com.docker.compose.project=caseflow-release','--filter',`label=com.docker.compose.service=${service}`]);
assert.match(found,/^[a-f0-9]+$/,'Exactly one owned dependency must be running');
const inspected=JSON.parse(docker(['inspect',found]))[0];
const id=ownedDependency(inspected,service);
function applicationProcesses() {
  return ['api','worker'].map(name=>{
    const selected=docker(['ps','-q','--filter','label=com.docker.compose.project=caseflow-release','--filter',`label=com.docker.compose.service=${name}`]);
    assert.match(selected,/^[a-f0-9]+$/);
    const container=JSON.parse(docker(['inspect',selected]))[0];
    return {service:name,id:container.Id,startedAt:container.State.StartedAt,restarts:container.RestartCount,image:container.Image};
  });
}
const auth=sessions({issuer:'http://127.0.0.1:18180/realms/caseflow',redirectUri:'http://127.0.0.1:18080/',password:values.DEMO_PASSWORD});
const path=`/tenants/${fixture.tenantId}`;
async function api(actor,route,method='GET',body,expected=200) {
  const response=await fetch('http://127.0.0.1:18080/api/v1'+route,{method,
    headers:{Authorization:`Bearer ${await auth.token(actor)}`,'Content-Type':'application/json','Idempotency-Key':randomUUID()},
    body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(20000)});
  assert.equal(response.status,expected,`${method} route status`);
  return response.json();
}
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function until(check,seconds) {
  const deadline=Date.now()+seconds*1000;
  while(Date.now()<deadline) {const result=await check();if(result)return result;await sleep(2000);}
  throw new Error('Bounded recovery condition timed out');
}
async function alertState() {
  const response=await fetch('http://127.0.0.1:19090/api/v1/alerts',{signal:AbortSignal.timeout(10000)});
  assert.equal(response.status,200);return response.json();
}
const result={service,containerId:id,image:inspected.Image,startedAt:new Date().toISOString(),events:[],revision:execFileSync('git',['rev-parse','HEAD'],{encoding:'utf8'}).trim()};
result.sourceSha256=createHash('sha256').update(readFileSync(new URL(import.meta.url))).digest('hex');
result.applicationBefore=applicationProcesses();
let item=await api('requester',path+'/cases','POST',{workflowId:fixture.workflowId,templateId:fixture.templateId,
  purchase:{vendor:'Synthetic dependency recovery',description:'Controlled local fault',currency:'USD',costCenter:'TRAINING',justification:'Synthetic failure evidence',lineItems:[{description:'Laptop',quantity:'1',unitPrice:'4200.00'}]}});
const casePath=path+'/cases/'+item.id;
item=await api('requester',casePath+'/assignments','PUT',{expectedVersion:item.version,approverIds:[fixture.users.manager,fixture.users.finance]});
item=await api('requester',casePath+'/start','POST',{expectedVersion:item.version});
item=await api('manager',casePath+'/actions','POST',{expectedVersion:item.version,action:'APPROVE'});
let stopped=false;
try {
  stopped=true; // Ambiguous CLI failure may still mean the daemon stopped it.
  docker(['stop','--time','10',id]);
  result.events.push({event:'dependency_stopped',at:new Date().toISOString()});
  if(service==='kafka') {
    item=await api('finance',casePath+'/actions','POST',{expectedVersion:item.version,action:'APPROVE'});
    assert.equal(item.state,'APPROVED');
    const job=(await api('requester',casePath+'/documents')).items[0];
    assert.equal(job.status,'QUEUED');result.queuedJob=job.jobId;
  } else {
    const response=await fetch('http://127.0.0.1:18080/api/v1/health',{signal:AbortSignal.timeout(10000)});
    assert.equal(response.status,503);result.healthDuringOutage=response.status;
  }
  const expectedAlert=service==='postgres'?'CaseflowMetricsDatabaseUnavailable':'CaseflowKafkaMetricsUnavailable';
  const firing=await until(async()=>{const state=await alertState();return state.data.alerts.some(a=>a.labels.alertname===expectedAlert&&a.state==='firing')?state:null;},100);
  save('firing-alerts.json',firing);result.events.push({event:'diagnosed_alert_firing',at:new Date().toISOString(),alert:expectedAlert});
  docker(['start',id]);stopped=false;
  await until(async()=>{try{return (await fetch('http://127.0.0.1:18080/api/v1/health',{signal:AbortSignal.timeout(5000)})).status===200;}catch{return false;}},90);
  if(service==='postgres') item=await api('finance',casePath+'/actions','POST',{expectedVersion:item.version,action:'APPROVE'});
  const job=(await api('requester',casePath+'/documents')).items[0];
  const completed=await until(async()=>{const current=await api('requester',`${path}/jobs/${job.jobId}`);assert.notEqual(current.status,'FAILED');return current.status==='SUCCEEDED'?current:null;},120);
  if(result.queuedJob)assert.equal(completed.jobId,result.queuedJob);
  const download=await api('requester',`${casePath}/documents/${job.jobId}/download-url`,'POST');
  assert.equal(new URL(download.url).origin,'http://127.0.0.1:18333');
  const response=await fetch(download.url,{signal:AbortSignal.timeout(10000)});assert.equal(response.status,200);
  const bytes=Buffer.from(await response.arrayBuffer());assert.equal(createHash('sha256').update(bytes).digest('hex'),completed.sha256);
  const audit=await api('requester',casePath+'/audit');
  assert.equal(audit.items.filter(e=>e.eventType==='DOCUMENT_SUCCEEDED').length,1);
  await until(async()=>{const state=await alertState();return !state.data.alerts.some(a=>a.labels.alertname===expectedAlert)?state:null;},90);
  save('resolved-alerts.json',await alertState());
  result.events.push({event:'same_services_recovered',at:new Date().toISOString()});
  result.applicationAfter=applicationProcesses();
  assert.deepEqual(result.applicationAfter,result.applicationBefore,'The API and worker must recover without process replacement');
  result.caseId=item.id;result.jobId=job.jobId;result.sha256=completed.sha256;result.selectedBytes=bytes.length;result.completionAudits=1;result.passed=true;
} catch(error) {
  result.passed=false;result.errorType=error.constructor.name;throw error;
} finally {
  try {
    if(stopped)docker(['start',id]);
  } catch(error) {
    result.restorationFailed=true;result.restorationErrorType=error.constructor.name;
    throw new Error('Owned dependency restoration failed; inspect the saved result and restore its exact container ID');
  } finally {
    result.finishedAt=new Date().toISOString();save('result.json',result);
  }
}
console.log(`PASS isolated ${service} restart, firing/resolved alert, same service recovery and one verified document; ${directory}`);
