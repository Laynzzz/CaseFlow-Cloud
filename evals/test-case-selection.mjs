import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const runner = fileURLToPath(new URL('./run-live.mjs', import.meta.url));
const splits = {
  development: [{id: 'dev-a'}, {id: 'dev-b'}, {id: 'dev-c'}],
  heldout: [{id: 'held-a'}, {id: 'held-b'}],
};

function validate(...args) {
  // Strip credentials and fail immediately if validation ever attempts network access.
  return spawnSync(process.execPath, ['--import',
    'data:text/javascript,globalThis.fetch=()=>{throw new Error("Unexpected network access")}',
    runner, '--validate-only', ...args], {
    encoding: 'utf8', timeout: 10000,
    env: {SystemRoot: process.env.SystemRoot, PATH: process.env.PATH},
  });
}

test('CLI validates an explicitly ordered subset and reports its IDs without provider access', () => {
  const result = validate('--ids', 'equipment-003,equipment-001');
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(JSON.parse(result.stdout), {
    datasetVersion: 'synthetic-v1', split: 'development', selected: 2,
    selectedIds: ['equipment-003', 'equipment-001'], providerCalls: 0, qualityMeasured: false,
  });
});

test('selector preserves full split and first-N behavior without mutating frozen inputs', async () => {
  const {selectCases} = await import('./case-selection.mjs');
  const original = structuredClone(splits);
  assert.deepEqual(selectCases(splits).map(c => c.id), ['dev-a', 'dev-b', 'dev-c']);
  assert.deepEqual(selectCases(splits, {limit: '2'}).map(c => c.id), ['dev-a', 'dev-b']);
  assert.deepEqual(selectCases(splits, {split: 'heldout'}).map(c => c.id), ['held-a', 'held-b']);
  assert.deepEqual(splits, original);
});

test('selector preserves caller order after trimming comma-separated IDs', async () => {
  const {selectCases} = await import('./case-selection.mjs');
  assert.deepEqual(selectCases(splits, {ids: ' dev-c, dev-a '}).map(c => c.id), ['dev-c', 'dev-a']);
  assert.deepEqual(selectCases(splits, {split: 'heldout', ids: 'held-b,held-a'}).map(c => c.id), ['held-b', 'held-a']);
});

test('selector rejects ambiguous, duplicated, absent and wrong-split selections', async () => {
  const {selectCases} = await import('./case-selection.mjs');
  for (const ids of ['', ' ', ',dev-a', 'dev-a,', 'dev-a, ,dev-b']) {
    assert.throws(() => selectCases(splits, {ids}), /empty/i);
  }
  assert.throws(() => selectCases(splits, {ids: 'dev-a, dev-a'}), /duplicate/i);
  assert.throws(() => selectCases(splits, {ids: 'dev-a', limit: '1'}), /--ids.*--limit/);
  assert.throws(() => selectCases(splits, {ids: 'absent'}), /unknown/i);
  assert.throws(() => selectCases(splits, {ids: 'held-a'}), /selected split/i);
  assert.throws(() => selectCases(splits, {split: 'heldout', ids: 'dev-a'}), /selected split/i);
  assert.throws(() => selectCases(splits, {split: 'other'}), /Split/);
  for (const limit of ['0', '-1', '1.5', '4', 'bad']) {
    assert.throws(() => selectCases(splits, {limit}), /Limit/);
  }
});

test('CLI rejects invalid ID options before creating any live run', () => {
  for (const [args, expected] of [
    [['--ids', 'equipment-001', '--limit', '1'], /--ids.*--limit/],
    [['--ids', 'equipment-001,equipment-001'], /Duplicate case ID/],
    [['--ids', 'equipment-001,'], /empty/],
    [['--ids', 'absent'], /Unknown case ID/],
    [['--ids', 'audio-001'], /selected split/],
  ]) {
    const result = validate(...args);
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, expected);
    assert.doesNotMatch(result.stderr, /Unexpected network access/);
  }
});

test('explicit heldout selection still requires reference review in validation mode', () => {
  const result = validate('--split', 'heldout', '--ids', 'audio-001');
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /reference review/);
});

test('CLI retains limit and full-split validation with selected IDs recorded', () => {
  const limited = validate('--limit', '1');
  assert.equal(limited.status, 0, limited.stderr);
  assert.deepEqual(JSON.parse(limited.stdout).selectedIds, ['equipment-001']);
  const full = validate();
  assert.equal(full.status, 0, full.stderr);
  assert.equal(JSON.parse(full.stdout).selected, 60);
  assert.equal(JSON.parse(full.stdout).selectedIds.length, 60);
});
