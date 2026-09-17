import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

test('predeclared fixtures match across a rotated nine-task comparison', async () => {
  const {comparisonPlan} = await import('./workflow-comparison-live.mjs');
  const plan = comparisonPlan();
  assert.equal(plan.fixtures.length, 3);
  assert.deepEqual(plan.tasks.map(t => t.mode), [
    'manual', 'extraction-only', 'grounded-review',
    'extraction-only', 'grounded-review', 'manual',
    'grounded-review', 'manual', 'extraction-only',
  ]);
  assert.equal(plan.maximumIntendedModelCalls, 9);
  for (const fixture of plan.fixtures) {
    assert.equal(plan.tasks.filter(t => t.fixtureId === fixture.id).length, 3);
    assert.equal(fixture.initialPurchase[fixture.requiredField], '');
    assert.ok(fixture.expectedPurchase[fixture.requiredField]);
    assert.equal(fixture.expectedPurchase.lineItems.length, 1);
  }
});

test('actual field comparison normalizes decimal formatting but preserves omissions and disagreements', async () => {
  const {purchaseDifferences, comparisonPlan} = await import('./workflow-comparison-live.mjs');
  const expected = comparisonPlan().fixtures[0].expectedPurchase;
  const same = structuredClone(expected);
  same.total = '374.500';
  same.lineItems[0].quantity = '2.0';
  assert.deepEqual(purchaseDifferences(same, expected), []);
  same.vendor = '';
  same.total = null;
  same.lineItems[0].unitPrice = '187.26';
  assert.deepEqual(purchaseDifferences(same, expected).map(row => row.field), ['vendor', 'lineItems', 'total']);
});

test('validation needs no credentials or network and live mode requires explicit new output', () => {
  const runner = fileURLToPath(new URL('./workflow-comparison-live.mjs', import.meta.url));
  const run = args => spawnSync(process.execPath, ['--import',
    'data:text/javascript,globalThis.fetch=()=>{throw new Error("Unexpected network access")}', runner, ...args], {
    encoding: 'utf8', timeout: 10000, env: {SystemRoot: process.env.SystemRoot, PATH: process.env.PATH},
  });
  const validation = run(['--validate-only']);
  assert.equal(validation.status, 0, validation.stderr);
  const output = JSON.parse(validation.stdout);
  assert.equal(output.plan.tasks.length, 9);
  assert.equal(output.providerCalls, 0);
  assert.equal(output.qualityMeasured, false);
  const refused = run(['--live']);
  assert.notEqual(refused.status, 0);
  assert.match(refused.stderr, /--output/);
  assert.doesNotMatch(refused.stderr, /Unexpected network access/);
});
