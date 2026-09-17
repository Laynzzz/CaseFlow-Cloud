export function localUrl(value) {
  const url=new URL(value);
  if(url.protocol!=='http:' || !['127.0.0.1','localhost','[::1]'].includes(url.hostname) || url.username || url.password) throw new Error('Load endpoints must use loopback HTTP');
  return url.href.replace(/\/$/,'');
}
export function loadConfig(env) {
  const integer=(key,fallback,min,max)=>{
    const n=Number(env[key]??fallback);
    if(!Number.isInteger(n)||n<min||n>max) throw new Error(`${key} must be an integer between ${min} and ${max}`);
    return n;
  };
  const rate=integer('LOAD_RATE',2,1,2),warmupSeconds=integer('LOAD_WARMUP_SECONDS',30,0,30),durationSeconds=integer('LOAD_DURATION_SECONDS',180,10,180);
  return {apiUrl:localUrl(env.LOAD_API_URL??'http://127.0.0.1:18080'),
    issuer:localUrl(env.LOAD_OIDC_ISSUER??'http://127.0.0.1:18180/realms/caseflow'),
    redirectUri:localUrl(env.LOAD_REDIRECT_URI??'http://127.0.0.1:18080')+'/',
    rate,warmupSeconds,durationSeconds,drainSeconds:integer('LOAD_DRAIN_SECONDS',120,10,120),
    vus:integer('LOAD_VUS',10,1,10),offeredIterations:rate*(warmupSeconds+durationSeconds),
    fixtureVersion:'synthetic-manual-purchase-load-v1', seed:20260917, readFraction:0.8, tenantDistribution:[0.5,0.5]};
}
export function classifyIteration(index) { return {tenantIndex:index%2,kind:index%10>=8?'document':'read'}; }
export function distribution(values) {
  const sorted=values.filter(Number.isFinite).sort((a,b)=>a-b);
  if(!sorted.length)return {count:0,p50:null,p95:null,max:null};
  return {count:sorted.length,p50:sorted[Math.ceil(sorted.length*0.5)-1],p95:sorted[Math.ceil(sorted.length*0.95)-1],max:sorted.at(-1)};
}
export function summarizeJobs(jobs) {
  const completed=jobs.filter(j=>j.state==='SUCCEEDED').length,failed=jobs.filter(j=>j.state==='FAILED').length;
  return {total:jobs.length,completed,failed,pending:jobs.length-completed-failed,allCompleted:jobs.length>0&&completed===jobs.length,
    completionMs:distribution(jobs.filter(j=>j.state==='SUCCEEDED').map(j=>j.observedAt-j.acknowledgedAt))};
}
export function parseHistogram(text,name,kind) {
  const result={buckets:{},sum:0,count:0};
  for(const line of text.split('\n')) {
    if(!line.startsWith(name+'_') || (kind&&!line.includes(`kind="${kind}"`)))continue;
    const value=Number(line.split(' ').at(-1));
    if(line.startsWith(name+'_bucket')) {const le=line.match(/le="([^"]+)"/); if(le)result.buckets[le[1]]=(result.buckets[le[1]]??0)+value;}
    if(line.startsWith(name+'_sum'))result.sum+=value;
    if(line.startsWith(name+'_count'))result.count+=value;
  }
  return result;
}
