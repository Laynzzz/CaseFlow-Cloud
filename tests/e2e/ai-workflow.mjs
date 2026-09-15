// Shared real-API helpers. Authentication tokens remain in memory.
import assert from 'node:assert/strict';

export async function uploadIndexedSource(actor, bearer, tenant, {kind, text, name, draft}) {
  const bytes=Buffer.from(text);
  let value=await actor(tenant+'/sources', {method:'POST', body:{name, kind, mediaType:'text/plain', byteSize:bytes.length,
    ...(draft ? {caseId:draft.id, expectedCaseVersion:draft.version} : {})}});
  const path=`${tenant}/sources/${value.id}`;
  const response=await fetch(`http://127.0.0.1:8080/api/v1${path}/content`, {method:'PUT', headers:{Authorization:`Bearer ${bearer}`, 'Content-Type':'application/octet-stream'}, body:bytes, signal:AbortSignal.timeout(20000)});
  assert.equal(response.status,200,'Synthetic source upload failed');
  await actor(path+'/finalize', {method:'POST', body:{expectedVersion:0, ...(draft ? {expectedCaseVersion:draft.version} : {})}});
  for (let i=0;i<80;i++) {
    value=await actor(path);
    if(value.state==='INDEXED') return value;
    assert.notEqual(value.state,'FAILED',value.failureCode);
    await new Promise(resolve=>setTimeout(resolve,750));
  }
  throw new Error('Source indexing timed out');
}

export async function waitAssistantJob(actor, path, requested) {
  for(let i=0;i<100;i++) {
    const job=(await actor(path)).items.find(item=>item.jobId===requested.jobId);
    if(job && ['SUCCEEDED','FAILED'].includes(job.status)) return job;
    await new Promise(resolve=>setTimeout(resolve,750));
  }
  throw new Error('Assistant job timed out');
}
