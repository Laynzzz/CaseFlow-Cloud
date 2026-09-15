// Paid opt-in evaluation through the deployed application, never direct model calls.
import {readFileSync,writeFileSync,appendFileSync,mkdirSync,existsSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {resolve,join} from 'node:path';
import {parseArgs} from 'node:util';
import {createHash} from 'node:crypto';
import {client,signIn} from '../tests/e2e/oidc-session.mjs';
import {uploadIndexedSource,waitAssistantJob} from '../tests/e2e/ai-workflow.mjs';
import {loadFrozenDataset,requireAnnotationReview} from './dataset.mjs';

const {values}=parseArgs({options:{live:{type:'boolean'},'validate-only':{type:'boolean'},split:{type:'string',default:'development'},limit:{type:'string'},output:{type:'string'},'annotation-review':{type:'string'}}});
const root=fileURLToPath(new URL('.',import.meta.url));
const {manifest,splits}=loadFrozenDataset(root);
if(!['development','heldout'].includes(values.split)) throw new Error('Split must be development or heldout');
const limit=values.limit===undefined ? splits[values.split].length : Number(values.limit);
if(!Number.isInteger(limit)||limit<1||limit>splits[values.split].length) throw new Error('Limit must be a positive count within this split');
const cases=splits[values.split].slice(0,limit);
if(values['validate-only']) {
  console.log(JSON.stringify({datasetVersion:manifest.version,split:values.split,selected:cases.length,providerCalls:0,qualityMeasured:false}));
  process.exit(0);
}
if(!values.live||!values.output) throw new Error('Requires --live, --output NEW_DIRECTORY and an approved shared AI budget');
if(values.split==='heldout') {
  requireAnnotationReview(manifest,values['annotation-review'] ? JSON.parse(readFileSync(values['annotation-review'],'utf8')) : null);
}
const directory=resolve(values.output);
if(existsSync(directory)) throw new Error('Output directory already exists; use a new directory to preserve prior evidence');
mkdirSync(directory,{recursive:true});
const metadata={startedAt:new Date().toISOString(),datasetVersion:manifest.version,split:values.split,
  datasetSha256:manifest.files[values.split+'.jsonl'].sha256,selectedIds:cases.map(c=>c.id),
  transport:'real-oidc-api-kafka-worker',selection:'first N in frozen file order',releaseGatePassed:false,
  note:'Synthetic diagnostic run. Reference and claim review required; failed calls need ledger reconciliation.'};
writeFileSync(join(directory,'run.json'),JSON.stringify(metadata,null,2)+'\n',{flag:'wx'});
writeFileSync(join(directory,'predictions.jsonl'),'',{flag:'wx'});
let stopped=false;
for(const item of cases) {
  const record={id:item.id,startedAt:new Date().toISOString(),sourceMap:{},policySources:[]};
  try {
    // Separate tenant per case gives the annotated corpus exact boundaries, including empty corpora.
    // Every tenant still spends against the same global database ledger.
    const token=await signIn('admin'), actor=client(token);
    const organization=await actor('/tenants',{method:'POST',body:{name:`Synthetic eval ${item.id} ${Date.now()}`}});
    const tenant=`/tenants/${organization.id}`;
    record.tenantId=organization.id;
    const purchase={vendor:'',description:item.purchase.description,currency:'USD',costCenter:item.purchase.costCenter??'',justification:'',lineItems:[]};
    let draft=await actor(tenant+'/cases',{method:'POST',body:{purchase}});
    record.caseId=draft.id;
    for(const passage of item.policyPassages) {
      let source=await uploadIndexedSource(actor,token,tenant,{kind:'POLICY',text:passage.text,name:`Synthetic ${passage.id}`});
      source=await actor(`${tenant}/sources/${source.id}/publish`,{method:'POST',body:{expectedVersion:source.version}});
      const chunks=await actor(`${tenant}/sources/${source.id}/chunks`);
      record.sourceMap[source.id]=passage.id;
      record.policySources.push({passageId:passage.id,source,chunks});
    }
    record.quote=await uploadIndexedSource(actor,token,tenant,{kind:'QUOTE',text:item.quote,name:`Synthetic ${item.id} quote`,draft});
    draft=await actor(`${tenant}/cases/${draft.id}`);
    record.policyPins=await actor(`${tenant}/cases/${draft.id}/policies/refresh`,{method:'POST',body:{expectedVersion:draft.version}});
    draft=await actor(`${tenant}/cases/${draft.id}`);
    record.manualPurchase=draft.purchase;record.revision=draft.version;
    const path=`${tenant}/cases/${draft.id}/assistant`;
    for(const kind of ['EXTRACTION','REVIEW']) {
      const requested=await actor(path,{method:'POST',body:{kind,expectedVersion:draft.version,...(kind==='EXTRACTION'?{sourceId:record.quote.id}:{})}});
      // Persist the logical job ID before waiting, including interruption/timeout evidence.
      record[kind.toLowerCase()]=requested;
      writeFileSync(join(directory,`${item.id}.json`),JSON.stringify(record,null,2)+'\n');
      const job=await waitAssistantJob(actor,path,requested);
      record[kind.toLowerCase()]=job;
      if(job.status==='FAILED' && /PROVIDER|BUDGET|CONFIGURED/.test(job.failureCode??'')) {
        stopped=true;break; // Avoid spending on an entire suite after a provider/admission failure.
      }
    }
    const evidence=record.review?.result?.evidence??{};
    const ranked=record.review?.result?.retrievedChunkIds;
    if(record.review?.status==='SUCCEEDED' && !Array.isArray(ranked)) throw new Error('Review result has no explicit retrieval rank');
    record.retrievedPassageIds=[...new Set((ranked??[]).map(chunkId=>{
      const chunk=evidence[chunkId];
      if(!chunk) throw new Error('Ranked chunk is missing its evidence');
      const id=record.sourceMap[chunk.sourceId];
      if(!id) throw new Error('Retrieved source is outside the annotated corpus');
      return id;
    }))];
    record.finishedAt=new Date().toISOString();
  } catch(error) {
    // Test API errors contain only application problem text; never include tokens/headers.
    record.failure=error.message;stopped=true;
  }
  writeFileSync(join(directory,`${item.id}.json`),JSON.stringify(record,null,2)+'\n');
  appendFileSync(join(directory,'predictions.jsonl'),JSON.stringify(record)+'\n');
  console.log(`${item.id}: extraction=${record.extraction?.status??'NOT_RUN'} review=${record.review?.status??'NOT_RUN'}`);
  if(stopped) break;
}
const bytes=readFileSync(join(directory,'predictions.jsonl'));
metadata.finishedAt=new Date().toISOString();metadata.stoppedEarly=stopped;
metadata.predictionsSha256=createHash('sha256').update(bytes).digest('hex');
writeFileSync(join(directory,'run.json'),JSON.stringify(metadata,null,2)+'\n');
if(stopped) process.exitCode=1;
