// Paid opt-in check for a complete purchase. Uses the existing shared AI ledger.
import assert from 'node:assert/strict';
import { mkdirSync, writeFileSync, existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { parseArgs } from 'node:util';
import { client, signIn } from './oidc-session.mjs';
import { uploadIndexedSource, waitAssistantJob } from './ai-workflow.mjs';

const { values } = parseArgs({ options: { live: { type: 'boolean' }, output: { type: 'string' } } });
if (!values.live || !values.output) throw new Error('Requires --live, --output NEW_JSON and existing budget authorization');
const output = resolve(values.output);
if (existsSync(output)) throw new Error('Preserve prior evidence: output already exists');
mkdirSync(dirname(output), { recursive: true });
const run = { startedAt: new Date().toISOString(), method: 'automated-live-api-check', humanVerified: false,
  scope: 'Complete synthetic purchase; schema maxItems=0; no claim-quality or user-outcome score', checks: [] };
writeFileSync(output, JSON.stringify(run, null, 2)+'\n', { flag: 'wx' });
const save = () => writeFileSync(output, JSON.stringify(run, null, 2)+'\n');
try {
  const token = await signIn('admin'), actor = client(token);
  const organization = await actor('/tenants', { method: 'POST', body: { name: `Synthetic complete review ${Date.now()}` } });
  run.tenantId = organization.id;
  const tenant = `/tenants/${organization.id}`;
  let draft = await actor(`${tenant}/cases`, { method: 'POST', body: { purchase: {
    vendor: 'Synthetic Equipment Ltd', description: 'Equipment purchase', currency: 'USD',
    costCenter: 'OPS', justification: 'Replace synthetic equipment',
    lineItems: [{ description: 'Equipment', quantity: '2', unitPrice: '2100.00' }],
  } } });
  run.caseId = draft.id;
  let policy = await uploadIndexedSource(actor, token, tenant, { kind: 'POLICY', name: 'Synthetic complete-purchase policy',
    text: 'Equipment purchases require a cost center before approval.' });
  policy = await actor(`${tenant}/sources/${policy.id}/publish`, { method: 'POST', body: { expectedVersion: policy.version } });
  run.policy = policy;
  await actor(`${tenant}/cases/${draft.id}/policies/refresh`, { method: 'POST', body: { expectedVersion: draft.version } });
  draft = await actor(`${tenant}/cases/${draft.id}`);
  run.manualPurchase = draft.purchase;
  const path = `${tenant}/cases/${draft.id}/assistant`;
  run.review = await actor(path, { method: 'POST', body: { kind: 'REVIEW', expectedVersion: draft.version } });
  save();
  run.review = await waitAssistantJob(actor, path, run.review);
  save();
  assert.equal(run.review.status, 'SUCCEEDED', run.review.failureCode);
  assert.equal(run.review.result.schemaVersion, 'purchase-review-v5');
  assert.equal(run.review.result.promptVersion, 'purchase-review-2026-09-16-v6');
  assert.deepEqual(run.review.result.output.missing_information, []);
  assert.equal(run.review.result.output.insufficient_evidence, false);
  assert.ok(run.review.result.output.policy_findings.length > 0);
  assert.deepEqual((await actor(`${tenant}/cases/${draft.id}`)).purchase, draft.purchase);
  run.checks.push('Complete purchase returned no missing fields; relevant cited finding; purchase unchanged');
  run.finishedAt = new Date().toISOString();
  save();
  console.log('PASS complete purchase review with no missing fields; evidence '+output);
} catch (error) {
  run.failure = error.message;
  save();
  throw error;
}
