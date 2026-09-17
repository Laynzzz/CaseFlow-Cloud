import {test} from 'node:test';
import assert from 'node:assert/strict';
import {ownedDependency} from './release-guards.mjs';
test('dependency faults require exact isolated project and service ownership', () => {
  const value={Id:'a'.repeat(64),Config:{Labels:{'com.docker.compose.project':'caseflow-release','com.docker.compose.service':'postgres'}}};
  assert.equal(ownedDependency(value,'postgres'),value.Id);
  assert.throws(()=>ownedDependency(value,'worker'));
  assert.throws(()=>ownedDependency(value,'kafka'));
  assert.throws(()=>ownedDependency({...value,Id:'postgres'},'postgres'));
  assert.throws(()=>ownedDependency({...value,Config:{Labels:{...value.Config.Labels,'com.docker.compose.project':'caseflow-cloud'}}},'postgres'));
});
