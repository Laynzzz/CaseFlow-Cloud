import { readFileSync,writeFileSync,mkdirSync,existsSync } from 'node:fs';
import { randomBytes } from 'node:crypto';
const envFile=new URL('../.env',import.meta.url);
let contents=readFileSync(envFile,'utf8');
const values=Object.fromEntries(contents.split(/\r?\n/).filter(Boolean).map(line=>line.split('=')));
for(const name of ['DEMO_PASSWORD','KEYCLOAK_ADMIN_PASSWORD']) {
  if(!values[name]) {values[name]=randomBytes(20).toString('hex');contents+=`${name}=${values[name]}\n`;}
}
writeFileSync(envFile,contents);
const users=['requester','manager','finance','admin','auditor','outsider'];
const realm={realm:'caseflow',enabled:true,registrationAllowed:false,resetPasswordAllowed:false,
  sslRequired:'none',accessTokenLifespan:300,
  clients:[{clientId:'caseflow-web',name:'CaseFlow browser',enabled:true,publicClient:true,
    standardFlowEnabled:true,directAccessGrantsEnabled:false,
    redirectUris:['http://127.0.0.1:5173/*'],webOrigins:['http://127.0.0.1:5173'],
    attributes:{'pkce.code.challenge.method':'S256','post.logout.redirect.uris':'http://127.0.0.1:5173/*'},
    protocolMappers:[{name:'caseflow-api audience',protocol:'openid-connect',protocolMapper:'oidc-audience-mapper',config:{'included.custom.audience':'caseflow-api','access.token.claim':'true'}}]}],
  users:users.map((username,i)=>({id:`00000000-0000-4000-8000-${String(i+1).padStart(12,'0')}`,username,enabled:true,
    firstName:username,lastName:'Demo',email:`${username}@caseflow.example`,emailVerified:true,
    credentials:[{type:'password',value:values.DEMO_PASSWORD,temporary:false}]}))};
const dir=new URL('../infrastructure/local/generated/',import.meta.url);mkdirSync(dir,{recursive:true});
writeFileSync(new URL('caseflow-realm.json',dir),JSON.stringify(realm,null,2)+'\n');
console.log('Generated ignored local Keycloak fixtures. Six synthetic users; password is DEMO_PASSWORD in .env.');
