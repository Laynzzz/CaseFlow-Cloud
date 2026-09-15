import {client,signIn} from '../tests/e2e/oidc-session.mjs';
import {writeFileSync} from 'node:fs';
import {seedTemplate} from './seed-template.mjs';
const names=['admin','requester','manager','finance','auditor','outsider'];
const clients={},identities={};
for(const name of names) { clients[name]=client(await signIn(name)); identities[name]=await clients[name]('/me'); }
let acme=identities.admin.memberships.find(t=>t.name==='Acme Studio');
if(!acme) acme=await clients.admin('/tenants',{method:'POST',body:{name:'Acme Studio'}});
const path=`/tenants/${acme.id}`;
const existing=(await clients.admin(path+'/memberships')).items;
for(const [name,roles] of Object.entries({admin:['ADMIN','REQUESTER'],requester:['REQUESTER'],manager:['APPROVER'],finance:['APPROVER'],auditor:['AUDITOR']})) {
  const found=existing.find(m=>m.userId===identities[name].id);
  if(!found) await clients.admin(path+'/memberships',{method:'PUT',key:`seed-${name}-membership`,body:{userId:identities[name].id,roles,active:true}});
}
let workflow=(await clients.admin(path+'/workflows')).items.find(w=>w.name==='Manager then Finance'&&w.published);
if(!workflow) {
  workflow=await clients.admin(path+'/workflows',{method:'POST',key:'seed-two-step-workflow',body:{name:'Manager then Finance',steps:['Manager review','Finance review']}});
  if(!workflow.published) workflow=await clients.admin(path+`/workflows/${workflow.id}/publish`,{method:'POST',key:'seed-publish-workflow',body:{expectedVersion:workflow.version}});
}
let northstar=identities.outsider.memberships.find(t=>t.name==='Northstar Workshop');
if(!northstar) northstar=await clients.outsider('/tenants',{method:'POST',body:{name:'Northstar Workshop'}});
const templateId=await seedTemplate(acme.id);
writeFileSync(new URL('../infrastructure/local/generated/demo-ids.json',import.meta.url),JSON.stringify({acmeId:acme.id,northstarId:northstar.id,workflowId:workflow.id,templateId,users:Object.fromEntries(names.map(name=>[name,identities[name].id]))},null,2));
console.log('Seeded two synthetic organizations, five Acme roles, and a published two-step workflow. No tokens written.');
