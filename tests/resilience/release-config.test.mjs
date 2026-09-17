import {test} from 'node:test';
import assert from 'node:assert/strict';
import {smokeConfig} from '../../scripts/release-config.mjs';

test('default smoke targets the isolated loopback release',()=>{
  assert.equal(smokeConfig().origin,'http://127.0.0.1:18080');
});
test('explicit cloud smoke requires HTTPS origins and an immutable local helper image',()=>{
  const input={origin:'https://app.example.test',issuer:'https://auth.example.test/realms/caseflow',storageOrigin:'https://bucket.s3.us-east-1.amazonaws.com',runtimeImage:'sha256:'+'a'.repeat(64),envFile:'.env.cloud-smoke',stateDirectory:'infrastructure/release/generated/cloud'};
  assert.equal(smokeConfig(input).workerHealthUrl,null);
  for(const replacement of [{origin:'http://app.example.test'},{origin:'https://user:pass@app.example.test'},{origin:'https://app.example.test/path'},{issuer:'https://auth.example.test/realms/caseflow?token=x'},{storageOrigin:'http://bucket.example.test'},{runtimeImage:'python:latest'},{envFile:''},{stateDirectory:''}]) {
    assert.throws(()=>smokeConfig({...input,...replacement}));
  }
});
