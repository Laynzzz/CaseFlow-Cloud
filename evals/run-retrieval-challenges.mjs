// Supplementary development probes. Never modify or substitute the held-out dataset.
import {readFileSync,writeFileSync,appendFileSync,mkdirSync,existsSync} from 'node:fs';
import {resolve,join} from 'node:path';
import {parseArgs} from 'node:util';
import {createHash} from 'node:crypto';
import {client,signIn} from '../tests/e2e/oidc-session.mjs';
import {uploadIndexedSource,waitAssistantJob} from '../tests/e2e/ai-workflow.mjs';
const {values}=parseArgs({options:{live:{type:'boolean'},output:{type:'string'}}});
if(!values.live||!values.output)throw new Error('Requires --live and a new --output directory; uses the approved shared AI ceiling');
const bytes=readFileSync(new URL('./retrieval-challenges.json',import.meta.url)),dataset=JSON.parse(bytes);
const directory=resolve(values.output);if(existsSync(directory))throw new Error('Output already exists');mkdirSync(directory,{recursive:true});
const run={datasetVersion:dataset.version,datasetSha256:createHash('sha256').update(bytes).digest('hex'),startedAt:new Date().toISOString(),selectedIds:dataset.cases.map(c=>c.id),releaseGatePassed:false};
writeFileSync(join(directory,'run.json'),JSON.stringify(run,null,2)+'\n',{flag:'wx'});
writeFileSync(join(directory,'predictions.jsonl'),'',{flag:'wx'});
for(const item of dataset.cases){
  const record={id:item.id,query:item.query,sourceMap:{},sources:[],reference:{relevantPassages:[item.id+'-policy']}};
  try{
    const token=await signIn('admin'),actor=client(token);
    const org=await actor('/tenants',{method:'POST',body:{name:`Synthetic retrieval ${item.id} ${Date.now()}`}}),tenant=`/tenants/${org.id}`;
    record.tenantId=org.id;
    const draft=await actor(tenant+'/cases',{method:'POST',body:{purchase:{vendor:'',description:item.query,currency:'USD',costCenter:'',justification:'',lineItems:[]}}});
    record.caseId=draft.id;
    // Insert distractors first so the expected answer is not favored by corpus input order.
    const passages=[...dataset.distractors.map((text,i)=>({id:`distractor-${i+1}`,text})),{id:item.id+'-policy',text:item.relevantPolicy}];
    for(const passage of passages){
      let source=await uploadIndexedSource(actor,token,tenant,{kind:'POLICY',text:passage.text,name:'Synthetic '+passage.id});
      source=await actor(`${tenant}/sources/${source.id}/publish`,{method:'POST',body:{expectedVersion:source.version}});
      record.sources.push({source,passage});record.sourceMap[source.id]=passage.id;
    }
    await actor(`${tenant}/cases/${draft.id}/policies/refresh`,{method:'POST',body:{expectedVersion:draft.version}});
    const current=await actor(`${tenant}/cases/${draft.id}`),path=`${tenant}/cases/${draft.id}/assistant`;
    record.review=await actor(path,{method:'POST',body:{kind:'REVIEW',expectedVersion:current.version,compareRetrieval:true}});
    writeFileSync(join(directory,item.id+'.json'),JSON.stringify(record,null,2)+'\n');
    record.review=await waitAssistantJob(actor,path,record.review);
    if(record.review.status!=='SUCCEEDED')throw new Error('Comparison failed: '+record.review.failureCode);
    const comparison=record.review.result.retrievalComparison;
    if(comparison.query!==record.review.result.retrievalQuery)throw new Error('Comparison query mismatch');
    const corpus=new Map(comparison.corpus.map(row=>[row.chunkId,row.sourceId]));
    record.retrievalComparisons={};
    for(const [method,key] of [['fullText','baselineChunkIds'],['semantic','semanticChunkIds'],['hybrid','hybridChunkIds']]){
      record.retrievalComparisons[method]=comparison[key].map(id=>{
        const passage=record.sourceMap[corpus.get(id)];if(!passage)throw new Error('Foreign comparison source');return passage;
      });
    }
    console.log(item.id+': '+JSON.stringify(record.retrievalComparisons));
  }catch(error){record.failure=error.message;process.exitCode=1;}
  writeFileSync(join(directory,item.id+'.json'),JSON.stringify(record,null,2)+'\n');
  appendFileSync(join(directory,'predictions.jsonl'),JSON.stringify(record)+'\n');
  if(record.failure)break;
}
run.finishedAt=new Date().toISOString();run.predictionsSha256=createHash('sha256').update(readFileSync(join(directory,'predictions.jsonl'))).digest('hex');
writeFileSync(join(directory,'run.json'),JSON.stringify(run,null,2)+'\n');
