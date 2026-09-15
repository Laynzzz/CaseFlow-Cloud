import { writeFileSync } from 'node:fs';
const ref = name => ({ $ref: `#/components/schemas/${name}` });
const str = { type: 'string' };
const uuid = { type: 'string', format: 'uuid' };
const bool = { type: 'boolean' };
const version = { type: 'integer', minimum: 0 };
const array = items => ({ type: 'array', items });
const object = (properties, required = Object.keys(properties)) => ({ type: 'object', additionalProperties: false, properties, required });
const nullable = schema => ({ ...schema, nullable: true });
const roles = { type: 'array', minItems: 1, uniqueItems: true, items: { type: 'string', enum: ['ADMIN','REQUESTER','APPROVER','AUDITOR'] } };
const schemas = {
  Health: object({status:{enum:['UP'],type:'string'},service:{enum:['case-api'],type:'string'},database:{enum:['UP'],type:'string'},schemaVersion:{enum:['1'],type:'string'}}),
  Problem: object({type:str,title:str,status:{type:'integer'},detail:str,instance:str,retryable:bool},['type','title','status','detail']),
  Tenant: object({id:uuid,name:str}),
  TenantMembership: object({id:uuid,name:str,roles,version,active:bool}),
  Me: object({id:uuid,displayName:str,memberships:array(ref('TenantMembership'))}),
  Membership: object({userId:uuid,displayName:str,roles,active:bool,version}),
  Memberships: object({items:array(ref('Membership'))}),
  MembershipInput: object({userId:uuid,roles,active:bool,expectedVersion:nullable(version)},['userId','roles','active']),
  TenantInput: object({name:{type:'string',minLength:1,maxLength:120}}),
  Workflow: object({id:uuid,name:str,steps:array(str),published:bool,version}),
  Workflows: object({items:array(ref('Workflow'))}),
  WorkflowInput: object({name:{type:'string',minLength:1,maxLength:120},steps:{type:'array',minItems:2,maxItems:2,items:{type:'string',minLength:1,maxLength:80}},expectedVersion:nullable(version)},['name','steps']),
  VersionInput: object({expectedVersion:version}),
  RetryInput: object({expectedAttempt:{type:'integer',minimum:1}}),
  Template: object({id:uuid,name:str,state:{type:'string',enum:['UPLOADING','VALIDATED','PUBLISHED']},version,byteSize:{type:'integer'},sha256:nullable(str)}),
  Templates: object({items:array(ref('Template'))}),
  TemplateInput: object({name:{type:'string',minLength:1,maxLength:120},byteSize:{type:'integer',minimum:1,maximum:10485760}}),
  Uploaded: object({uploaded:bool}),
  Source: object({id:uuid,kind:{type:'string',enum:['QUOTE','POLICY']},caseId:nullable(uuid),name:str,mediaType:str,state:{type:'string',enum:['UPLOADING','INDEXING','INDEXED','FAILED','PUBLISHED','DEACTIVATED']},version,byteSize:{type:'integer'},sha256:nullable(str),jobId:nullable(uuid),failureCode:nullable(str)}),
  Sources: object({items:array(ref('Source'))}),
  SourceInput: object({name:{type:'string',minLength:1,maxLength:120},kind:{type:'string',enum:['QUOTE','POLICY']},caseId:nullable(uuid),mediaType:{type:'string',enum:['text/plain','application/pdf']},byteSize:{type:'integer',minimum:1,maximum:10485760},expectedCaseVersion:nullable(version)},['name','kind','mediaType','byteSize']),
  SourceVersionInput: object({expectedVersion:version,expectedCaseVersion:nullable(version)},['expectedVersion']),
  SourceChunk: object({id:uuid,page:{type:'integer'},section:str,start:{type:'integer'},end:{type:'integer'},text:str,sha256:str}),
  SourceChunks: object({source:ref('Source'),metadata:object({parserVersion:str,chunkVersion:str,pageCount:{type:'integer'}}),items:array(ref('SourceChunk'))}),
  PolicyPin: object({id:uuid,name:str,version,state:str}),
  PolicyPins: object({initialized:bool,items:array(ref('PolicyPin'))}),
  PolicyPassage: object({id:uuid,sourceId:uuid,name:str,page:{type:'integer'},section:str,start:{type:'integer'},end:{type:'integer'},text:str,sha256:str,score:{type:'number'}}),
  PolicySearch: object({method:str,items:array(ref('PolicyPassage'))}),
  AICitation: object({chunkId:str,quote:str}),
  AIText: object({value:nullable(str),citations:array(ref('AICitation'))}),
  AIItems: object({value:nullable(array(ref('LineItem'))),citations:array(ref('AICitation'))}),
  AIExtraction: object({vendor:ref('AIText'),currency:ref('AIText'),total:ref('AIText'),lineItems:ref('AIItems'),warnings:array(str)}),
  AIReview: object({summary:str,missing_information:array(str),policy_findings:array(object({claim:str,citations:array(ref('AICitation'))})),citations:array(ref('AICitation')),insufficient_evidence:bool}),
  AIEvidence: object({sourceId:uuid,page:{type:'integer'},start:{type:'integer'},text:str}),
  AIResult: object({output:{oneOf:[ref('AIExtraction'),ref('AIReview')]},model:str,promptVersion:str,schemaVersion:str,promptHash:str,schemaHash:str,callId:uuid,elapsedMs:{type:'integer'},inputTokens:{type:'integer'},outputTokens:{type:'integer'},estimatedCostUsd:str,pricingVersion:str,revision:version,retrievalMethod:str,evidence:{type:'object',additionalProperties:ref('AIEvidence')}}),
  AIJob: object({jobId:uuid,kind:{type:'string',enum:['EXTRACTION','REVIEW']},status:str,failureCode:nullable(str),revision:version,stale:bool,result:nullable(ref('AIResult'))}),
  AIJobs: object({enabled:bool,items:array(ref('AIJob'))}),
  AIRun: object({kind:{type:'string',enum:['EXTRACTION','REVIEW']},expectedVersion:version,sourceId:nullable(uuid),compareRetrieval:bool},['kind','expectedVersion']),
  AIAccept: object({expectedVersion:version,fields:{type:'array',minItems:1,maxItems:3,uniqueItems:true,items:{type:'string',enum:['vendor','currency','lineItems']}}}),
  AIAccepted: object({accepted:bool,version}),
  Document: object({jobId:uuid,attempt:{type:'integer'},status:str,failureCode:nullable(str),sha256:nullable(str),byteSize:nullable({type:'integer'}),createdAt:{type:'string',format:'date-time'}}),
  Documents: object({items:array(ref('Document'))}),
  Download: object({url:str,expiresInSeconds:{type:'integer'}}),
  LineItem: object({description:{type:'string',maxLength:500},quantity:{type:'string',pattern:'^[0-9]+(\\.[0-9]{1,3})?$'},unitPrice:{type:'string',pattern:'^[0-9]+(\\.[0-9]{1,4})?$'}}),
  PurchaseInput: object({vendor:{type:'string',maxLength:200},description:{type:'string',maxLength:2000},currency:{type:'string',minLength:3,maxLength:3},costCenter:{type:'string',maxLength:100},justification:{type:'string',maxLength:4000},lineItems:{type:'array',maxItems:100,items:ref('LineItem')}}),
  Purchase: object({vendor:str,description:str,currency:str,costCenter:str,justification:str,lineItems:array(ref('LineItem')),total:str}),
  CaseInput: object({purchase:ref('PurchaseInput'),workflowId:nullable(uuid),templateId:nullable(uuid),originalCaseId:nullable(uuid),expectedVersion:nullable(version)},['purchase']),
  Assignment: object({step:{type:'integer'},userId:uuid,displayName:str,outcome:nullable(str)}),
  AssignInput: object({expectedVersion:version,approverIds:{type:'array',minItems:2,maxItems:2,items:uuid}}),
  ActionInput: object({expectedVersion:version,action:{type:'string',enum:['APPROVE','REJECT','CANCEL','COMMENT']},comment:{type:'string',maxLength:4000}},['expectedVersion','action']),
  Case: object({id:uuid,ownerId:uuid,state:{type:'string',enum:['DRAFT','ACTIVE','APPROVED','REJECTED','CANCELLED']},purchase:ref('Purchase'),workflowId:nullable(uuid),templateId:nullable(uuid),originalCaseId:nullable(uuid),version,createdAt:{type:'string',format:'date-time'},updatedAt:{type:'string',format:'date-time'},documentStatus:nullable(str),assignments:array(ref('Assignment'))}),
  CasePage: object({items:array(ref('Case')),nextCursor:nullable(str)}),
  Audit: object({id:uuid,actorId:uuid,eventType:str,details:{type:'object',additionalProperties:true},createdAt:{type:'string',format:'date-time'}}),
  AuditPage: object({items:array(ref('Audit')),nextCursor:nullable(str)}),
};
Object.assign(schemas.AIResult.properties,{sourceId:nullable(uuid),sourceVersion:nullable(version),sourceSha256:nullable(str)});
// Optional for historical results written before rank provenance was introduced.
Object.assign(schemas.AIResult.properties,{retrievalQuery:nullable(str),retrievedChunkIds:array(uuid)});
schemas.AIResult.properties.retrievalComparison={type:'object',additionalProperties:true};
schemas.AIResult.required.push('sourceId','sourceVersion','sourceSha256');
const paths = {};
function endpoint(path, method, operationId, output, input, {auth=true,command=false,list=false}={}) {
  const parameters = [...path.matchAll(/\{(\w+)\}/g)].map(([,name]) => ({name,in:'path',required:true,schema:uuid}));
  if (command) parameters.push({name:'Idempotency-Key',in:'header',required:true,schema:{type:'string',minLength:8,maxLength:128}});
  if(list) parameters.push({name:'cursor',in:'query',schema:str},{name:'limit',in:'query',schema:{type:'integer',minimum:1,maximum:100,default:25}});
  if(operationId==='listCases') parameters.push({name:'state',in:'query',schema:{type:'string',enum:['DRAFT','ACTIVE','APPROVED','REJECTED','CANCELLED']}},{name:'assignedToMe',in:'query',schema:bool});
  const responses = {'200':{description:'Success',content:{'application/json':{schema:ref(output)}}}};
  for(const code of ['400','401','403','404','409','503']) responses[code]={description:'Structured error; inaccessible resources return 404',content:{'application/problem+json':{schema:ref('Problem')}}};
  (paths[path]??={})[method]={operationId,security:auth?[{bearerAuth:[]}]:[],parameters,responses,...(input?{requestBody:{required:true,content:{'application/json':{schema:ref(input)}}}}:{})};
}
endpoint('/api/v1/health','get','getHealth','Health',null,{auth:false});
endpoint('/api/v1/me','get','getMe','Me');
endpoint('/api/v1/tenants','post','createTenant','Tenant','TenantInput');
const t='/api/v1/tenants/{tenantId}';
endpoint(t+'/sources','get','listSources','Sources');
paths[t+'/sources'].get.parameters.push({name:'caseId',in:'query',schema:uuid});
endpoint(t+'/sources','post','allocateSource','Source','SourceInput',{command:true});
endpoint(t+'/sources/{sourceId}','get','getSource','Source');
endpoint(t+'/sources/{sourceId}/chunks','get','sourceChunks','SourceChunks');
paths[t+'/sources/{sourceId}/chunks'].get.parameters.push({name:'caseId',in:'query',schema:uuid});
endpoint(t+'/sources/{sourceId}/content','put','uploadSource','Uploaded');
paths[t+'/sources/{sourceId}/content'].put.requestBody={required:true,content:{'application/octet-stream':{schema:{type:'string',format:'binary'}}}};
for(const action of ['finalize','publish','deactivate']) endpoint(t+'/sources/{sourceId}/'+action,'post',action+'Source','Source','SourceVersionInput',{command:true});
endpoint(t+'/memberships','get','listMemberships','Memberships');
endpoint(t+'/memberships','put','saveMembership','Membership','MembershipInput',{command:true});
endpoint(t+'/workflows','get','listWorkflows','Workflows');
endpoint(t+'/workflows','post','createWorkflow','Workflow','WorkflowInput',{command:true});
endpoint(t+'/workflows/{workflowId}','put','updateWorkflow','Workflow','WorkflowInput',{command:true});
endpoint(t+'/workflows/{workflowId}/publish','post','publishWorkflow','Workflow','VersionInput',{command:true});
endpoint(t+'/templates','get','listTemplates','Templates');
endpoint(t+'/templates','post','allocateTemplate','Template','TemplateInput',{command:true});
endpoint(t+'/templates/{templateId}/content','put','uploadTemplate','Uploaded');
paths[t+'/templates/{templateId}/content'].put.requestBody={required:true,content:{'application/octet-stream':{schema:{type:'string',format:'binary'}}}};
endpoint(t+'/templates/{templateId}/finalize','post','finalizeTemplate','Template','VersionInput',{command:true});
endpoint(t+'/templates/{templateId}/publish','post','publishTemplate','Template','VersionInput',{command:true});
endpoint(t+'/cases','get','listCases','CasePage',null,{list:true});
endpoint(t+'/cases','post','createCase','Case','CaseInput',{command:true});
endpoint(t+'/cases/{caseId}','get','getCase','Case');
endpoint(t+'/cases/{caseId}/assistant','get','assistantJobs','AIJobs');
endpoint(t+'/cases/{caseId}/assistant','post','runAssistant','AIJob','AIRun',{command:true});
endpoint(t+'/cases/{caseId}/assistant/{jobId}/accept','post','acceptSuggestions','AIAccepted','AIAccept',{command:true});
endpoint(t+'/cases/{caseId}/policies','get','casePolicies','PolicyPins');
endpoint(t+'/cases/{caseId}/policies/refresh','post','refreshPolicies','PolicyPins','VersionInput',{command:true});
endpoint(t+'/cases/{caseId}/policies/search','get','searchPolicies','PolicySearch');
paths[t+'/cases/{caseId}/policies/search'].get.parameters.push({name:'query',in:'query',required:true,schema:{type:'string',minLength:1,maxLength:500}});
endpoint(t+'/cases/{caseId}','put','updateCase','Case','CaseInput',{command:true});
endpoint(t+'/cases/{caseId}/assignments','put','assignCase','Case','AssignInput',{command:true});
endpoint(t+'/cases/{caseId}/start','post','startCase','Case','VersionInput',{command:true});
endpoint(t+'/cases/{caseId}/actions','post','actOnCase','Case','ActionInput',{command:true});
endpoint(t+'/cases/{caseId}/audit','get','getAudit','AuditPage',null,{list:true});
endpoint(t+'/cases/{caseId}/documents','get','listDocuments','Documents');
endpoint(t+'/cases/{caseId}/documents/{jobId}/download-url','post','downloadDocument','Download');
endpoint(t+'/jobs/{jobId}','get','getJob','Document');
endpoint(t+'/jobs/{jobId}/retry','post','retryJob','Document','RetryInput',{command:true});
const contract={openapi:'3.0.3',info:{title:'CaseFlow API',version:'0.2.0',description:'Phase 0/1 contracts. See docs/contracts.md for permissions and command semantics. Success responses use 200, including command replay.'},paths,components:{securitySchemes:{bearerAuth:{type:'http',scheme:'bearer',bearerFormat:'JWT'}},schemas}};
writeFileSync(new URL('../contracts/openapi/caseflow.yaml',import.meta.url),JSON.stringify(contract,null,2)+'\n');
console.log('Generated OpenAPI (JSON is valid YAML).');
