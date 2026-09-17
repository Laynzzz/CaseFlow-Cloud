import assert from 'node:assert/strict';

function address(value,pathAllowed=false) {
  const url=new URL(value);
  assert.ok(url.protocol==='https:'||(url.protocol==='http:'&&url.hostname==='127.0.0.1'),'HTTPS required outside loopback');
  assert.ok(!url.username&&!url.password&&!url.search&&!url.hash,'URL must not contain credentials, query or fragment');
  assert.ok(pathAllowed||url.pathname==='/','Expected an origin without a path');
  return pathAllowed?url.href.replace(/\/$/,''):url.origin;
}
export function smokeConfig(input) {
  if(!input)return {origin:'http://127.0.0.1:18080',issuer:'http://127.0.0.1:18180/realms/caseflow',storageOrigin:'http://127.0.0.1:18333',workerHealthUrl:'http://127.0.0.1:18090/health',envFile:'infrastructure/release/generated/.env',stateDirectory:'infrastructure/release/generated',runtimeImage:null};
  assert.match(input.runtimeImage??'',/^sha256:[a-f0-9]{64}$/,'Supply the already built local helper image ID');
  assert.ok(typeof input.envFile==='string'&&input.envFile.length>0,'Supply an ignored credential file');
  assert.ok(typeof input.stateDirectory==='string'&&input.stateDirectory.length>0,'Supply an isolated evidence-state directory');
  return {...input,origin:address(input.origin),issuer:address(input.issuer,true),storageOrigin:address(input.storageOrigin),workerHealthUrl:input.workerHealthUrl?address(input.workerHealthUrl,true):null};
}
