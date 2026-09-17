import {createHash,randomBytes} from 'node:crypto';

// Based on tests/e2e/oidc-session.mjs; configurable isolated release ports and refresh.
// Neither credentials, cookies nor tokens leave process memory / private loopback IPC.
export function sessions({issuer,redirectUri,password}) {
  const cache=new Map(),pending=new Map();
  async function exchange(body) {
    const response=await fetch(`${issuer}/protocol/openid-connect/token`,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams(body),signal:AbortSignal.timeout(20000)});
    if(!response.ok)throw new Error(`OIDC token exchange status ${response.status}`);
    const data=await response.json();
    return {...data,expiresAt:Date.now()+data.expires_in*1000};
  }
  async function login(username) {
    const verifier=randomBytes(32).toString('base64url'),state=randomBytes(16).toString('hex'),cookies=new Map();
    async function request(url,options={}) {
      if(new URL(url).origin!==new URL(issuer).origin)throw new Error('OIDC form origin mismatch');
      const response=await fetch(url,{...options,redirect:'manual',headers:{...options.headers,Cookie:[...cookies].map(([k,v])=>`${k}=${v}`).join('; ')},signal:AbortSignal.timeout(20000)});
      for(const cookie of response.headers.getSetCookie()){const part=cookie.split(';')[0],index=part.indexOf('=');cookies.set(part.slice(0,index),part.slice(index+1));}
      return response;
    }
    const params=new URLSearchParams({client_id:'caseflow-web',redirect_uri:redirectUri,response_type:'code',scope:'openid',state,code_challenge:createHash('sha256').update(verifier).digest('base64url'),code_challenge_method:'S256'});
    let page=await request(`${issuer}/protocol/openid-connect/auth?${params}`);
    const form=(await page.text()).match(/<form[^>]*id="kc-form-login"[^>]*action="([^"]+)"/);
    if(!form)throw new Error('Expected synthetic OIDC login form');
    page=await request(form[1].replaceAll('&amp;','&'),{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({username,password,credentialId:''})});
    const location=page.headers.get('location');
    if(!location||!location.startsWith(redirectUri))throw new Error('Synthetic OIDC login did not complete');
    const callback=new URL(location);
    if(callback.searchParams.get('state')!==state)throw new Error('OIDC state mismatch');
    return exchange({grant_type:'authorization_code',client_id:'caseflow-web',code:callback.searchParams.get('code'),redirect_uri:redirectUri,code_verifier:verifier});
  }
  async function token(name) {
    const previous=cache.get(name);
    if(previous&&previous.expiresAt>Date.now()+30000)return previous.access_token;
    if(!pending.has(name)) pending.set(name,(async()=>{
      const next=previous?await exchange({grant_type:'refresh_token',client_id:'caseflow-web',refresh_token:previous.refresh_token}):await login(name);
      cache.set(name,next);return next.access_token;
    })().finally(()=>pending.delete(name)));
    return pending.get(name);
  }
  return {token};
}
