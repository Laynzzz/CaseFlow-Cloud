import http from 'k6/http';
import exec from 'k6/execution';
import {Counter,Trend} from 'k6/metrics';
import {classifyIteration} from './model.mjs';

const cfg=JSON.parse(__ENV.LOAD_CONFIG);
const failures=new Counter('workload_failures');
const reads=new Counter('read_iterations_completed');
const approved=new Counter('document_approvals_acknowledged');
const acknowledgement=new Trend('application_http_ack_ms',true);
const approvalAck=new Trend('final_approval_ack_ms',true);
const budgetRefusals=new Counter('arrival_budget_refusals');
const scenarios={mixed:{executor:'constant-arrival-rate',rate:cfg.rate,timeUnit:'1s',duration:`${cfg.warmupSeconds+cfg.durationSeconds}s`,preAllocatedVUs:cfg.vus,maxVUs:cfg.vus,gracefulStop:'20s'}};
export const options={scenarios,systemTags:['status','method','name','scenario','expected_response'],discardResponseBodies:false,
  summaryTrendStats:['avg','min','med','max','p(90)','p(95)','p(99)'],
  thresholds:{'workload_failures':['count==0'],'dropped_iterations':['count==0'],'http_req_failed{scope:application}':['rate==0'],
    'application_http_ack_ms{phase:sustained}':['p(95)<2000'],'final_approval_ack_ms{phase:sustained}':['p(95)<2000'],
    'http_reqs{scope:application,phase:sustained}':['count>0'],'read_iterations_completed{phase:sustained}':['count>0'],
    'document_approvals_acknowledged{phase:sustained}':['count>0']}};

function bridge(path,body) {
  const r=http.request(body?'POST':'GET',__ENV.LOAD_BRIDGE+path,body?JSON.stringify(body):null,{headers:{Authorization:`Bearer ${__ENV.LOAD_BRIDGE_SECRET}`,'Content-Type':'application/json'},tags:{name:'load_harness_bridge',scope:'harness'},timeout:'15s'});
  if(r.status!==200)throw new Error('Harness bridge failed');
  return r.json();
}
export default function() {
  const phase=exec.instance.currentTestRunDuration<cfg.warmupSeconds*1000?'warmup':'sustained',index=exec.scenario.iterationInTest,selection=classifyIteration(index),tenant=cfg.tenants[selection.tenantIndex];
  budgetRefusals.add(0);
  if(index>=cfg.offeredIterations){budgetRefusals.add(1);return;}
  const base=`/tenants/${tenant.id}/cases`,keyPrefix=`${cfg.runId}-${phase}-${index}`;
  failures.add(0,{phase});
  try {
    const tokens=bridge('/tokens');
    let serial=0;
    function api(name,path,method='GET',body,label='case_read') {
      const r=http.request(method,cfg.apiUrl+'/api/v1'+path,body?JSON.stringify(body):null,{headers:{Authorization:`Bearer ${tokens[name]}`,'Content-Type':'application/json','Idempotency-Key':`${keyPrefix}-${serial++}`},tags:{name:label,scope:'application',phase},timeout:'10s'});
      acknowledgement.add(r.timings.duration,{phase,operation:label});
      if(label==='final_approve')approvalAck.add(r.timings.duration,{phase});
      if(r.status!==200)throw new Error(`${label}: HTTP ${r.status}`);
      return r.json();
    }
    if(selection.kind==='read') {
      api('requester',base+'?limit=20','GET',null,'case_list');
      api('requester',base+'/'+tenant.readCaseIds[index%tenant.readCaseIds.length]);
      reads.add(1,{phase});return;
    }
    let item=api('requester',base,'POST',{purchase:cfg.purchase,workflowId:tenant.workflowId,templateId:tenant.templateId},'case_create');
    const path=base+'/'+item.id;
    bridge('/case',{tenantIndex:selection.tenantIndex,caseId:item.id,phase,createdAt:Date.now()});
    item=api('requester',path+'/assignments','PUT',{expectedVersion:item.version,approverIds:[cfg.users.manager,cfg.users.finance]},'assign');
    item=api('requester',path+'/start','POST',{expectedVersion:item.version},'start');
    item=api('manager',path+'/actions','POST',{expectedVersion:item.version,action:'APPROVE'},'first_approve');
    const approvalStartedAt=Date.now();
    item=api('finance',path+'/actions','POST',{expectedVersion:item.version,action:'APPROVE'},'final_approve');
    if(item.state!=='APPROVED')throw new Error('Final approval state mismatch');
    bridge('/approved',{caseId:item.id,acknowledgedAt:Date.now(),approvalStartedAt});
    approved.add(1,{phase});
  } catch(error) {failures.add(1,{phase});console.error(`Iteration failed: ${String(error.message).slice(0,120)}`);}
}
export function handleSummary(data){return {[__ENV.LOAD_SUMMARY]:JSON.stringify(data,null,2)};}
