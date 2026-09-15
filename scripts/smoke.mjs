import assert from 'node:assert/strict';

const origin = process.argv.slice(2).find(value => value.startsWith('http')) ?? 'http://127.0.0.1:8080';
const expectUnavailable = process.argv.includes('--unavailable');
const response = await fetch(`${origin}/api/v1/health`, { signal: AbortSignal.timeout(10000) });
if (expectUnavailable) {
  assert.equal(response.status, 503, 'Unavailable database must produce 503');
  assert.match(response.headers.get('content-type') ?? '', /application\/problem\+json/);
  const problem = await response.json();
  assert.equal(problem.status, 503);
  assert.equal(problem.detail, 'The database is not ready. Try again shortly.');
} else {
  assert.equal(response.status, 200, 'API and migrated database must be ready');
  assert.deepEqual(await response.json(), {
    status: 'UP', service: 'case-api', database: 'UP', schemaVersion: '1',
  });
}
const denied = await fetch(`${origin}/api/v1/me`, { signal: AbortSignal.timeout(10000) });
assert.equal(denied.status, 401, 'Business routes require a verified identity');
console.log(`PASS ${origin}: ${expectUnavailable ? 'unavailable' : 'ready'} response matches contract; business route denied.`);
