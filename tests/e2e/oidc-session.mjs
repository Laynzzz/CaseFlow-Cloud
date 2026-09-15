import { createHash,randomBytes } from 'node:crypto';
import { readFileSync } from 'node:fs';
export function localEnv() {
  return Object.fromEntries(readFileSync(new URL('../../.env',import.meta.url),'utf8').split(/\r?\n/).filter(Boolean).map(line=>line.split('=')));
}
// Test-only Authorization Code + PKCE client. Tokens stay in memory and are never logged.
export async function signIn(username,clientId='caseflow-web') {
  const verifier=randomBytes(32).toString('base64url');
  const state=randomBytes(16).toString('hex');
  const cookies=new Map();
  async function request(url,options={}) {
    const response=await fetch(url,{...options,redirect:'manual',headers:{...options.headers,Cookie:[...cookies].map(([k,v])=>`${k}=${v}`).join('; ')},signal:AbortSignal.timeout(20000)});
    for(const cookie of response.headers.getSetCookie()) {
      const part=cookie.split(';')[0], index=part.indexOf('=');cookies.set(part.slice(0,index),part.slice(index+1));
    }
    return response;
  }
  const issuer='http://127.0.0.1:8180/realms/caseflow';
  const params=new URLSearchParams({client_id:clientId,redirect_uri:'http://127.0.0.1:5173/',response_type:'code',scope:'openid',state,code_challenge:createHash('sha256').update(verifier).digest('base64url'),code_challenge_method:'S256'});
  let page=await request(`${issuer}/protocol/openid-connect/auth?${params}`);
  const html=await page.text();
  const form=html.match(/<form[^>]*id="kc-form-login"[^>]*action="([^"]+)"/);
  if(!form) throw new Error('Expected Keycloak login form');
  page=await request(form[1].replaceAll('&amp;','&'),{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({username,password:localEnv().DEMO_PASSWORD,credentialId:''})});
  const redirect=page.headers.get('location');
  if(!redirect || !redirect.startsWith('http://127.0.0.1:5173/')) throw new Error(`OIDC login did not complete for synthetic user ${username}`);
  const callback=new URL(redirect);
  if(callback.searchParams.get('state')!==state) throw new Error('OIDC state mismatch');
  const tokens=await fetch(`${issuer}/protocol/openid-connect/token`,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({grant_type:'authorization_code',client_id:clientId,code:callback.searchParams.get('code'),redirect_uri:'http://127.0.0.1:5173/',code_verifier:verifier}),signal:AbortSignal.timeout(20000)});
  if(!tokens.ok) throw new Error('Token exchange failed');
  return (await tokens.json()).access_token;
}
export function client(token) {
  return async (path,{method='GET',body,key,expected=200}={})=>{
    const result=await fetch(`http://127.0.0.1:8080/api/v1${path}`,{method,headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json',...(method==='GET'?{}:{'Idempotency-Key':key??crypto.randomUUID()})},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(15000)});
    const data=await result.json().catch(()=>({}));
    if(result.status!==expected) throw new Error(`${method} ${path}: expected ${expected}, got ${result.status}: ${data.detail??'no detail'}`);
    return data;
  };
}
