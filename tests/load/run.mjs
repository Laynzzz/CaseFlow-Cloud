import {readFileSync,writeFileSync,mkdirSync,readdirSync} from 'node:fs';
import {resolve,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash,randomBytes,randomUUID} from 'node:crypto';
import {createServer} from 'node:http';
import {spawn,execFileSync} from 'node:child_process';
import {promisify} from 'node:util';
import {execFile} from 'node:child_process';
import os from 'node:os';
import {loadConfig,localUrl,summarizeJobs,distribution,parseHistogram} from './model.mjs';
import {sessions} from './oidc.mjs';

const root=resolve(dirname(fileURLToPath(import.meta.url)),'../..');
process.env.LOAD_WORKER_METRICS_URL??='http://127.0.0.1:18090/metrics';
process.env.LOAD_API_METRICS_URL??='http://127.0.0.1:18081/actuator/prometheus';
process.env.LOAD_COMPOSE_PROJECT??='caseflow-release';
const config=loadConfig(process.env);
config.workerMetricsUrl=localUrl(process.env.LOAD_WORKER_METRICS_URL);
config.apiMetricsUrl=localUrl(process.env.LOAD_API_METRICS_URL);
config.composeProject=process.env.LOAD_COMPOSE_PROJECT;
config.traceSampling=process.env.LOAD_TRACE_SAMPLE_RATE??'not specified; inspect release evidence';
const runId=new Date().toISOString().replace(/[:.]/g,'-');
const output=resolve(process.env.LOAD_OUTPUT??resolve(root,'tests/load/results',runId));
mkdirSync(output,{recursive:true});
const save=(name,value)=>writeFileSync(resolve(output,name),typeof value==='string'||Buffer.isBuffer(value)?value:JSON.stringify(value,null,2)+'\n');
const command=(file,args)=>execFileSync(file,args,{cwd:root,encoding:'utf8',stdio:['ignore','pipe','pipe']}).trim();
const version=command('k6',['version']);
if(!version.startsWith('k6.exe v2.2.0 ')&&!version.startsWith('k6 v2.2.0 '))throw new Error('This workload pins k6 2.2.0; explicitly review a version change');
const revision=command('git',['rev-parse','HEAD']);
const sources=readdirSync(resolve(root,'tests/load')).filter(n=>/\.(mjs|js)$/.test(n)).sort();
save('environment.json',{startedAt:new Date().toISOString(),revision,dirty:command('git',['status','--porcelain']),version,node:process.version,os:{platform:os.platform(),release:os.release(),arch:os.arch(),cpuModel:os.cpus()[0]?.model,logicalCpus:os.cpus().length,totalMemoryBytes:os.totalmem()},config,runId,
  sourceSha256:Object.fromEntries(sources.map(name=>[name,createHash('sha256').update(readFileSync(resolve(root,'tests/load',name))).digest('hex')])),
  cacheState:'No cache flush; seeding and warmup precede measured arrivals',command:'node tests/load/run.mjs',
  limits:'Local synthetic short sustained experiment; no maximum capacity, cloud performance, or AI throughput claim.'});

const credentialsPath=resolve(process.env.LOAD_ENV_FILE??resolve(root,'infrastructure/release/generated/.env'));
const values=Object.fromEntries(readFileSync(credentialsPath,'utf8').split(/\r?\n/).filter(l=>l&&!l.startsWith('#')).map(l=>{const i=l.indexOf('=');return [l.slice(0,i),l.slice(i+1)];}));
if(!values.DEMO_PASSWORD)throw new Error('Missing synthetic DEMO_PASSWORD');
const auth=sessions({...config,password:values.DEMO_PASSWORD});
const names=['admin','requester','manager','finance','outsider'];
async function api(actor,path,{method='GET',body,expected=200,timeoutMs=15000}={}) {
  const response=await fetch(config.apiUrl+'/api/v1'+path,{method,headers:{Authorization:`Bearer ${await auth.token(actor)}`,'Content-Type':'application/json','Idempotency-Key':randomUUID()},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(timeoutMs)});
  if(response.status!==expected)throw new Error(`API ${method} expected ${expected}, received ${response.status}`);
  return response.json().catch(()=>({}));
}
const purchase={vendor:'Synthetic Load Tools',description:'Synthetic manual purchase load fixture',currency:'USD',costCenter:'TRAINING',justification:'Bounded synthetic reliability self-test',lineItems:[{description:'Laptop',quantity:'1',unitPrice:'4200.00'}]};
const jobs=new Map(),snapshots=[],samplingErrors=[],downloads=[],histograms={},reconciliations={},infrastructureTimes={};
let bridge,child,timer,polling=false,workloadStartedAt,arrivalStoppedAt,k6ExitCode,fixtures,observerRequests=0,observerBudgetExceeded=false;
const observerRequestLimit=1200;
const optionalText=async(envKey,file)=>{
  if(!process.env[envKey])return;
  try{const response=await fetch(localUrl(process.env[envKey]),{signal:AbortSignal.timeout(10000)});if(!response.ok)throw new Error(`status ${response.status}`);const body=await response.text();save(file,body);
    if(envKey==='LOAD_WORKER_METRICS_URL') {
      histograms[file]={queue:parseHistogram(body,'caseflow_job_queue_seconds','DOCUMENT'),execution:parseHistogram(body,'caseflow_job_execution_seconds','DOCUMENT')};
      for(const metric of ['caseflow_metrics_database_up','caseflow_kafka_metrics_up']) {
        if(!new RegExp(`^${metric} 1(?:\\.0)?$`,'m').test(body))samplingErrors.push({at:new Date().toISOString(),kind:'worker-metrics-unavailable',error:`${metric} missing or unhealthy`,snapshot:file});
      }
    }}
  catch(error){samplingErrors.push({at:new Date().toISOString(),kind:envKey,error:error.message});}
};
async function infrastructureSnapshot(label) {
  infrastructureTimes[label]={startedAt:Date.now()};
  await optionalText('LOAD_WORKER_METRICS_URL',`${label}-worker.prom`);
  await optionalText('LOAD_API_METRICS_URL',`${label}-api.prom`);
  if(process.env.LOAD_COMPOSE_PROJECT) {
    try {
      const execute=promisify(execFile),{stdout:ids}=await execute('docker',['ps','-q','--filter',`label=com.docker.compose.project=${process.env.LOAD_COMPOSE_PROJECT}`]);
      if(ids.trim()) {const containerIds=ids.trim().split(/\r?\n/);const {stdout}=await execute('docker',['stats','--no-stream','--format','{{json .}}',...containerIds],{timeout:20000});save(`${label}-containers.jsonl`,stdout);
        if(label==='before') {
          const {stdout:images}=await execute('docker',['inspect','--format','{{json .Id}} {{json .Config.Image}} {{json .Image}} {{.HostConfig.Memory}} {{.HostConfig.NanoCpus}}',...containerIds],{timeout:10000});
          save('container-images.txt','containerId configuredImage imageId memoryLimitBytes nanoCpuLimit\n'+images);
        }
      }
      else samplingErrors.push({kind:'docker-stats',error:'No containers matched configured project'});
      if(['before','after-drain'].includes(label)) {
        const {stdout:workerIds}=await execute('docker',['ps','-q','--filter',`label=com.docker.compose.project=${process.env.LOAD_COMPOSE_PROJECT}`,'--filter','label=com.docker.compose.service=worker']);
        const ids=workerIds.trim().split(/\r?\n/).filter(Boolean);
        if(ids.length!==1)throw new Error('Expected one isolated worker container');
        const {stdout}=await execute('docker',['exec',ids[0],'python','-c','import json; from caseflow_worker.reconciliation import reconcile; print(json.dumps(reconcile(age_seconds=60)))'],{timeout:20000});
        reconciliations[label]=JSON.parse(stdout);save(`${label}-reconciliation.json`,reconciliations[label]);
      }
    }catch {samplingErrors.push({kind:'docker-stats',error:'Container snapshot unavailable'});}
  }
  infrastructureTimes[label].finishedAt=Date.now();
}
async function observe(deadline=Date.now()+5000) {
  if(polling)return;polling=true;
  try {
    let requestsThisPass=0;
    for(const job of [...jobs.values()].sort((a,b)=>(a.lastCheckedAt??0)-(b.lastCheckedAt??0))) {
      if(Date.now()>=deadline||requestsThisPass>=10)break;
      if(['SUCCEEDED','FAILED'].includes(job.state))continue;
      if(observerRequests>=observerRequestLimit) {
        if(!observerBudgetExceeded)samplingErrors.push({kind:'observer-capacity-refused',error:'Observer request budget exhausted; pending backlog retained'});
        observerBudgetExceeded=true;break;
      }
      observerRequests++;requestsThisPass++;
      job.lastCheckedAt=Date.now();
      const tenant=fixtures.tenants[job.tenantIndex],base=`/tenants/${tenant.id}/cases/${job.caseId}`;
      try {
        const docs=(await api('requester',base+'/documents',{timeoutMs:Math.max(1,Math.min(2000,deadline-Date.now()))})).items;
        if(docs.length>1)throw new Error('Multiple logical document requests');
        if(!docs.length)continue;
        const doc=docs[0];
        job.jobId=doc.jobId;job.state=doc.status;job.requestedAt=doc.createdAt;
        if(doc.status==='SUCCEEDED') {
          job.observedAt=Date.now();job.sha256=doc.sha256;job.byteSize=doc.byteSize;
          if(!/^[a-f0-9]{64}$/.test(doc.sha256)||!doc.byteSize)throw new Error('Missing document artifact evidence');
        }
        if(doc.status==='FAILED')job.failureCode=doc.failureCode;
      }catch(error){samplingErrors.push({at:new Date().toISOString(),kind:'job-observation',error:error.message});}
    }
    snapshots.push({at:Date.now(),sinceStartMs:workloadStartedAt?Date.now()-workloadStartedAt:null,...summarizeJobs([...jobs.values()]),freeHostMemoryBytes:os.freemem(),harnessRssBytes:process.memoryUsage().rss});
  }finally{polling=false;}
}
try {
  const users={};for(const name of names)users[name]=(await api(name,'/me')).id;
  const bytes=readFileSync(resolve(process.env.LOAD_TEMPLATE??resolve(root,'infrastructure/release/generated/purchase-template.docx')));
  const tenants=[];
  for(const suffix of ['A','B']) {
    const tenant=await api('admin','/tenants',{method:'POST',body:{name:`Load ${runId} ${suffix}`}}),base=`/tenants/${tenant.id}`;
    for(const [name,roles] of Object.entries({requester:['REQUESTER'],manager:['APPROVER'],finance:['APPROVER']}))await api('admin',base+'/memberships',{method:'PUT',body:{userId:users[name],roles,active:true}});
    let workflow=await api('admin',base+'/workflows',{method:'POST',body:{name:'Synthetic load two step',steps:['Manager review','Finance review']}});
    workflow=await api('admin',base+`/workflows/${workflow.id}/publish`,{method:'POST',body:{expectedVersion:workflow.version}});
    let template=await api('admin',base+'/templates',{method:'POST',body:{name:'Synthetic load template',byteSize:bytes.length}});
    const upload=await fetch(config.apiUrl+'/api/v1'+base+`/templates/${template.id}/content`,{method:'PUT',headers:{Authorization:`Bearer ${await auth.token('admin')}`,'Content-Type':'application/octet-stream'},body:bytes,signal:AbortSignal.timeout(15000)});
    if(!upload.ok)throw new Error(`Template upload status ${upload.status}`);
    template=await api('admin',base+`/templates/${template.id}/finalize`,{method:'POST',body:{expectedVersion:template.version}});
    template=await api('admin',base+`/templates/${template.id}/publish`,{method:'POST',body:{expectedVersion:template.version}});
    const readCaseIds=[];
    for(let i=0;i<10;i++)readCaseIds.push((await api('requester',base+'/cases',{method:'POST',body:{purchase,workflowId:workflow.id,templateId:template.id}})).id);
    tenants.push({id:tenant.id,workflowId:workflow.id,templateId:template.id,readCaseIds});
  }
  fixtures={...config,runId,users,tenants,purchase};save('fixtures.json',fixtures);
  for(const tenant of tenants)await api('outsider',`/tenants/${tenant.id}/cases/${tenant.readCaseIds[0]}`,{expected:404});
  await api('requester',`/tenants/${tenants[0].id}/cases/${tenants[1].readCaseIds[0]}`,{expected:404});
  save('authorization.json',{unauthorizedActorDenied:2,wrongTenantResourceDenied:1,expectedStatus:404,skipped:0});
  const secret=randomBytes(32).toString('hex');
  bridge=createServer(async(req,res)=>{
    res.setHeader('Content-Type','application/json');res.setHeader('Cache-Control','no-store');
    if(req.headers.authorization!==`Bearer ${secret}`){res.writeHead(403);res.end('{}');return;}
    try {
      if(req.method==='GET'&&req.url==='/tokens'){const tokens={};for(const name of ['requester','manager','finance'])tokens[name]=await auth.token(name);res.end(JSON.stringify(tokens));return;}
      let body='';for await(const chunk of req){body+=chunk;if(body.length>4096)throw new Error('Bridge request too large');}
      const data=JSON.parse(body);
      if(req.url==='/case') {
        if(!/^[a-f0-9-]{36}$/.test(data.caseId)||![0,1].includes(data.tenantIndex)||!['warmup','sustained'].includes(data.phase)||jobs.size>=config.offeredIterations)throw new Error('Invalid load case');
        jobs.set(data.caseId,{...data,state:'CREATED'});
      }else if(req.url==='/approved'){const job=jobs.get(data.caseId);if(!job)throw new Error('Unknown approval');Object.assign(job,{...data,state:job.state==='CREATED'?'APPROVED':job.state});}
      else {res.writeHead(404);res.end('{}');return;}
      res.end('{}');
    }catch {res.writeHead(500);res.end('{}');}
  });
  await new Promise(resolve=>bridge.listen(0,'127.0.0.1',resolve));
  await infrastructureSnapshot('before');
  workloadStartedAt=Date.now();
  const trace=[];
  const childEnv={...process.env,LOAD_CONFIG:JSON.stringify(fixtures),LOAD_BRIDGE:`http://127.0.0.1:${bridge.address().port}`,LOAD_BRIDGE_SECRET:secret,LOAD_SUMMARY:resolve(output,'k6-summary.json')};
  // Child environment carries only bridge authorization; application tokens are obtained in memory.
  delete childEnv.DEMO_PASSWORD;
  // Ambient k6 debug/output settings could expose headers or export data remotely.
  for(const key of Object.keys(childEnv))if(key.startsWith('K6_'))delete childEnv[key];
  child=spawn('k6',['run','--quiet',resolve(root,'tests/load/mixed.k6.js')],{cwd:root,env:childEnv,stdio:['ignore','pipe','pipe']});
  for(const stream of [child.stdout,child.stderr])stream.on('data',chunk=>trace.push(chunk.toString()));
  const done=new Promise((resolve,reject)=>{child.once('error',reject);child.once('exit',resolve);});
  timer=setInterval(()=>void observe().catch(()=>samplingErrors.push({kind:'observer',error:'Snapshot failed'})),2000);
  const midpoint=setTimeout(()=>void infrastructureSnapshot('midpoint'),(config.warmupSeconds+config.durationSeconds/2)*1000);
  const warmupEnd=config.warmupSeconds?setTimeout(()=>void infrastructureSnapshot('after-warmup'),config.warmupSeconds*1000):null;
  const watchdog=setTimeout(()=>child.kill(),(config.warmupSeconds+config.durationSeconds+45)*1000);
  k6ExitCode=await done;clearTimeout(watchdog);clearTimeout(midpoint);if(warmupEnd)clearTimeout(warmupEnd);arrivalStoppedAt=Date.now();save('k6-console.txt',trace.join(''));
  await infrastructureSnapshot('after-arrivals');
  const drainDeadline=arrivalStoppedAt+config.drainSeconds*1000;
  while(Date.now()<drainDeadline) {
    await observe(Math.min(drainDeadline,Date.now()+5000));
    if([...jobs.values()].every(j=>['SUCCEEDED','FAILED'].includes(j.state)))break;
    await new Promise(resolve=>setTimeout(resolve,1000));
  }
  clearInterval(timer);while(polling)await new Promise(resolve=>setTimeout(resolve,100));
  // One verified download per tenant after drain, outside HTTP acknowledgement measurements.
  for(let index=0;index<2;index++) {
    const job=[...jobs.values()].find(j=>j.tenantIndex===index&&j.state==='SUCCEEDED');if(!job)continue;
    const path=`/tenants/${tenants[index].id}/cases/${job.caseId}/documents/${job.jobId}/download-url`;
    await api('outsider',path,{method:'POST',expected:404});
    const link=await api('requester',path,{method:'POST'}),response=await fetch(link.url,{signal:AbortSignal.timeout(15000)});
    if(!response.ok)throw new Error(`DOCX download status ${response.status}`);
    const bytes=Buffer.from(await response.arrayBuffer());
    if(createHash('sha256').update(bytes).digest('hex')!==job.sha256||bytes.length!==job.byteSize||bytes.subarray(0,2).toString()!=='PK')throw new Error('DOCX integrity mismatch');
    save(`tenant-${index}-sample.docx`,bytes);downloads.push({tenantIndex:index,caseId:job.caseId,sha256:job.sha256,byteSize:job.byteSize,outsiderDenied:true});
  }
  await infrastructureSnapshot('after-drain');
} catch(error) {
  save('failure.json',{at:new Date().toISOString(),message:error.message});process.exitCode=1;
} finally {
  if(timer)clearInterval(timer);while(polling)await new Promise(resolve=>setTimeout(resolve,100));
  if(child&&child.exitCode===null)child.kill();
  if(bridge)await new Promise(resolve=>bridge.close(resolve));
  const all=[...jobs.values()],summary=summarizeJobs(all),sustained=summarizeJobs(all.filter(j=>j.phase==='sustained'));
  const histogramDeltas=Object.fromEntries(['queue','execution'].map(kind=>{
    const before=histograms['before-worker.prom']?.[kind],after=histograms['after-drain-worker.prom']?.[kind];
    return [kind,before&&after?{count:after.count-before.count,sum:after.sum-before.sum,buckets:Object.fromEntries(Object.entries(after.buckets).map(([bound,count])=>[bound,count-(before.buckets[bound]??0)]))}:null];
  }));
  const histogramEvidenceComplete=Object.values(histogramDeltas).every(h=>h&&h.count>=summary.completed&&h.count>0);
  save('jobs.json',all);save('backlog.json',snapshots);save('sampling-errors.json',samplingErrors);save('downloads.json',downloads);
  save('infrastructure-snapshot-times.json',infrastructureTimes);
  save('worker-histograms.json',{snapshots:histograms,deltas:histogramDeltas,definition:'Cumulative server histograms; compare after-drain with before. Queue is claim minus readiness (available_at, or prior lease expiry for reclaimed running jobs), excluding deliberate backoff. Execution labels include outcome; raw Prometheus snapshots preserve labels.'});
  save('result.json',{runId,k6ExitCode,workloadStartedAt,arrivalStoppedAt,finishedAt:Date.now(),summary,sustained,
    completionFromApprovalStartMs:distribution(all.filter(j=>j.state==='SUCCEEDED').map(j=>j.observedAt-j.approvalStartedAt)),
    pollingIntervalMs:2000,observerRequests,observerRequestLimit,observerBudgetExceeded,completionDefinition:'API-visible SUCCEEDED observed by independent polling; includes poll-cycle and bounded round-robin observer delay (10 requests per pass)',
    drainLimitSeconds:config.drainSeconds,downloadsVerified:downloads.length,samplingErrors:samplingErrors.length,
    reconciliation:reconciliations,histogramEvidenceComplete,
    passed:process.exitCode!==1&&k6ExitCode===0&&summary.allCompleted&&downloads.length===2&&samplingErrors.length===0&&histogramEvidenceComplete&&Object.values(reconciliations).every(r=>r.status==='NO_FINDINGS')});
  if(k6ExitCode!==0||!summary.allCompleted||downloads.length!==2||samplingErrors.length||!histogramEvidenceComplete||Object.values(reconciliations).some(r=>r.status!=='NO_FINDINGS'))process.exitCode=1;
  console.log(`Load evidence retained: ${output}; completed=${summary.completed}, failed=${summary.failed}, pending=${summary.pending}, k6Exit=${k6ExitCode??'not started'}`);
}
