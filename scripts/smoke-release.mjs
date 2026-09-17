import assert from 'node:assert/strict';
import { createHash, randomBytes } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';

const origin = 'http://127.0.0.1:18080';
const issuer = 'http://127.0.0.1:18180/realms/caseflow';
const dir = new URL('../infrastructure/release/generated/', import.meta.url);
const env = Object.fromEntries(readFileSync(new URL('.env', dir), 'utf8').trim().split(/\r?\n/).map(line => line.split('=')));
const priorFile = new URL('release-ids.json', dir);
const prior = existsSync(priorFile) ? JSON.parse(readFileSync(priorFile, 'utf8')) : null;
const deadline = Date.now() + 120000;
while (true) {
  try { if ((await fetch(`${issuer}/.well-known/openid-configuration`)).ok) break; } catch {}
  if (Date.now() > deadline) throw new Error('Release identity provider did not become ready.');
  await new Promise(resolve => setTimeout(resolve, 1000));
}
for (const route of ['/', '/account', '/new', '/admin', '/cases/00000000-0000-4000-8000-000000000001']) {
  const page = await fetch(origin + route);
  assert.equal(page.status, 200, `Packaged SPA ${route}`);
  assert.match(await page.text(), /<div id="root"><\/div>/);
}
assert.equal((await fetch(`${origin}/api/v1/me`)).status, 401);
assert.equal((await fetch(`${origin}/actuator/prometheus`)).status, 401);
assert.equal((await fetch(`${origin}/api/v1/health`)).status, 200);
assert.equal((await fetch('http://127.0.0.1:18090/health')).status, 200);

async function signIn(username) {
  const verifier = randomBytes(32).toString('base64url'), state = randomBytes(16).toString('hex'), cookies = new Map();
  async function request(url, options = {}) {
    const response = await fetch(url, { ...options, redirect: 'manual', headers: { ...options.headers, Cookie: [...cookies].map(([k, v]) => `${k}=${v}`).join('; ') }, signal: AbortSignal.timeout(20000) });
    for (const cookie of response.headers.getSetCookie()) { const part = cookie.split(';')[0], index = part.indexOf('='); cookies.set(part.slice(0, index), part.slice(index + 1)); }
    return response;
  }
  const params = new URLSearchParams({ client_id: 'caseflow-web', redirect_uri: origin + '/', response_type: 'code', scope: 'openid', state, code_challenge: createHash('sha256').update(verifier).digest('base64url'), code_challenge_method: 'S256' });
  const page = await request(`${issuer}/protocol/openid-connect/auth?${params}`);
  const form = (await page.text()).match(/<form[^>]*id="kc-form-login"[^>]*action="([^"]+)"/);
  assert.ok(form, 'Release OIDC login form');
  const login = await request(form[1].replaceAll('&amp;', '&'), { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: new URLSearchParams({ username, password: env.DEMO_PASSWORD, credentialId: '' }) });
  const callback = new URL(login.headers.get('location'));
  assert.equal(callback.origin, origin); assert.equal(callback.searchParams.get('state'), state);
  const exchange = await fetch(`${issuer}/protocol/openid-connect/token`, { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: new URLSearchParams({ grant_type: 'authorization_code', client_id: 'caseflow-web', code: callback.searchParams.get('code'), redirect_uri: origin + '/', code_verifier: verifier }) });
  assert.equal(exchange.status, 200); return (await exchange.json()).access_token;
}
const tokens = {}, identities = {};
async function api(actor, path, method = 'GET', body, expected = 200) {
  const response = await fetch(`${origin}/api/v1${path}`, { method, headers: { Authorization: `Bearer ${tokens[actor]}`, 'Content-Type': 'application/json', ...(method === 'GET' ? {} : { 'Idempotency-Key': crypto.randomUUID() }) }, body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(20000) });
  const result = await response.json();
  assert.equal(response.status, expected, `${actor} ${method} ${path}: ${result.detail ?? ''}`); return result;
}
for (const actor of ['admin', 'requester', 'manager', 'finance', 'outsider']) {
  tokens[actor] = await signIn(actor); identities[actor] = await api(actor, '/me');
}
if (prior) {
  const previousCase = await api('requester', `/tenants/${prior.tenantId}/cases/${prior.caseId}`);
  assert.equal(previousCase.state, 'APPROVED'); assert.equal(previousCase.documentStatus, 'SUCCEEDED');
  const previousJob = await api('requester', `/tenants/${prior.tenantId}/jobs/${prior.jobId}`);
  assert.equal(previousJob.status, 'SUCCEEDED');
  if (prior.sha256) assert.equal(previousJob.sha256, prior.sha256, 'Deployment preserves the previously selected artifact');
}
let tenant = identities.admin.memberships.find(t => t.name === 'Release Acme Studio');
tenant ??= await api('admin', '/tenants', 'POST', { name: 'Release Acme Studio' });
const path = `/tenants/${tenant.id}`;
const existing = (await api('admin', path + '/memberships')).items;
for (const [actor, roles] of Object.entries({ admin: ['ADMIN', 'REQUESTER'], requester: ['REQUESTER'], manager: ['APPROVER'], finance: ['APPROVER'] })) {
  if (!existing.find(m => m.userId === identities[actor].id)) await api('admin', path + '/memberships', 'PUT', { userId: identities[actor].id, roles, active: true });
}
let workflow = (await api('admin', path + '/workflows')).items.find(w => w.name === 'Release two approvals' && w.published);
if (!workflow) {
  workflow = await api('admin', path + '/workflows', 'POST', { name: 'Release two approvals', steps: ['Manager review', 'Finance review'] });
  workflow = await api('admin', `${path}/workflows/${workflow.id}/publish`, 'POST', { expectedVersion: workflow.version });
}
// Generate a synthetic DOCX using the same pinned Python image; no host Python is required.
const worker = execFileSync('docker', ['ps', '--filter', 'label=com.docker.compose.project=caseflow-release', '--filter', 'label=com.docker.compose.service=worker', '--format', '{{.ID}}'], { encoding: 'utf8' }).trim();
assert.match(worker, /^[a-f0-9]+$/);
const template = execFileSync('docker', ['exec', worker, 'python', '-c', "import io,sys; from docx import Document; d=Document(); d.add_heading('Synthetic release purchase',0); [d.add_paragraph('{{ '+k+' }}') for k in ['vendor','total','description','cost_center','justification']]; b=io.BytesIO(); d.save(b); sys.stdout.buffer.write(b.getvalue())"]);
writeFileSync(new URL('purchase-template.docx', dir), template);
let published = (await api('admin', path + '/templates')).items.find(t => t.name === 'Release purchase v1' && t.state === 'PUBLISHED');
if (!published) {
  published = await api('admin', path + '/templates', 'POST', { name: 'Release purchase v1', byteSize: template.length });
  const upload = await fetch(`${origin}/api/v1${path}/templates/${published.id}/content`, { method: 'PUT', headers: { Authorization: `Bearer ${tokens.admin}`, 'Content-Type': 'application/octet-stream' }, body: template });
  assert.equal(upload.status, 200);
  published = await api('admin', `${path}/templates/${published.id}/finalize`, 'POST', { expectedVersion: published.version });
  published = await api('admin', `${path}/templates/${published.id}/publish`, 'POST', { expectedVersion: published.version });
}
let item = await api('requester', path + '/cases', 'POST', { workflowId: workflow.id, templateId: published.id, purchase: { vendor: 'Synthetic release vendor', description: 'Release smoke laptop', currency: 'USD', costCenter: 'TRAINING', justification: 'Synthetic deployment smoke', lineItems: [{ description: 'Laptop', quantity: '1', unitPrice: '4200.00' }] } });
const casePath = path + '/cases/' + item.id;
item = await api('requester', casePath + '/assignments', 'PUT', { expectedVersion: item.version, approverIds: [identities.manager.id, identities.finance.id] });
item = await api('requester', casePath + '/start', 'POST', { expectedVersion: item.version });
for (const actor of ['manager', 'finance']) item = await api(actor, casePath + '/actions', 'POST', { expectedVersion: item.version, action: 'APPROVE' });
assert.equal(item.state, 'APPROVED');
let job = (await api('requester', casePath + '/documents')).items[0];
const jobDeadline = Date.now() + 90000;
while (job.status !== 'SUCCEEDED' && Date.now() < jobDeadline) {
  assert.notEqual(job.status, 'FAILED');
  await new Promise(resolve => setTimeout(resolve, 500));
  job = await api('requester', `${path}/jobs/${job.jobId}`);
}
assert.equal(job.status, 'SUCCEEDED');
await api('outsider', casePath, 'GET', undefined, 404);
const download = await api('requester', `${casePath}/documents/${job.jobId}/download-url`, 'POST');
assert.equal(new URL(download.url).origin, 'http://127.0.0.1:18333');
const response = await fetch(download.url); assert.equal(response.status, 200);
const bytes = Buffer.from(await response.arrayBuffer());
assert.equal(createHash('sha256').update(bytes).digest('hex'), job.sha256); assert.equal(bytes.length, job.byteSize);
execFileSync('docker', ['exec', '-i', worker, 'python', '-c', "import io,sys; from docx import Document; t='\\n'.join(p.text for p in Document(io.BytesIO(sys.stdin.buffer.read())).paragraphs); assert 'Synthetic release vendor' in t; assert '4200.00' in t; assert '{{' not in t"], { input: bytes });
writeFileSync(new URL('release-ids.json', dir), JSON.stringify({ tenantId: tenant.id, workflowId: workflow.id, templateId: published.id, caseId: item.id, jobId: job.jobId, sha256: job.sha256, users: Object.fromEntries(Object.entries(identities).map(([name, identity]) => [name, identity.id])) }, null, 2) + '\n');
console.log(`PASS packaged SPA deep links, PKCE, API/operations denial, tenant denial, ${prior ? 'prior approved case preserved, ' : ''}two approvals, Kafka/worker completion and SHA-256 verified DOCX; synthetic case ${item.id}. No paid AI calls.`);
