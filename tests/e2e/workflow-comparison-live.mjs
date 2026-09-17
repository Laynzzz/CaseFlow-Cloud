// Opt-in, agent-operated API self-test. It measures no human work or usability.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {existsSync, mkdirSync, readFileSync, writeFileSync} from 'node:fs';
import {join, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {parseArgs} from 'node:util';
import {client, signIn} from './oidc-session.mjs';
import {uploadIndexedSource, waitAssistantJob} from './ai-workflow.mjs';

const MODES = ['manual', 'extraction-only', 'grounded-review'];
const QUOTE_FIELDS = ['vendor', 'currency', 'lineItems', 'total'];
const PURCHASE_FIELDS = ['vendor', 'description', 'currency', 'costCenter', 'justification', 'lineItems', 'total'];
const EDITABLE_QUOTE_FIELDS = ['vendor', 'currency', 'lineItems'];
const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');
const encode = value => JSON.stringify(value, null, 2) + '\n';

export function comparisonPlan() {
  const inputs = [
    {id: 'stand-replacement', vendor: 'Synthetic Maple Stand Workshop', item: 'Adjustable equipment stand',
      quantity: '2', unitPrice: '187.25', total: '374.50', requiredField: 'costCenter', costCenter: 'OPS-TEST',
      justification: 'Replace two demonstration equipment stands'},
    {id: 'archive-labels', vendor: 'Synthetic Pebble Label House', item: 'Reusable archive label pack',
      quantity: '3', unitPrice: '42.40', total: '127.20', requiredField: 'justification', costCenter: 'FIN-TEST',
      justification: 'Label three synthetic archive shelves'},
    {id: 'workbench-kits', vendor: 'Synthetic Birch Kit Studio', item: 'Workbench organizer kit',
      quantity: '4', unitPrice: '28.75', total: '115.00', requiredField: 'costCenter', costCenter: 'LAB-TEST',
      justification: 'Equip four demonstration workbenches'},
  ];
  const fixtures = inputs.map(input => {
    const expectedPurchase = {vendor: input.vendor, description: input.item, currency: 'USD',
      costCenter: input.costCenter, justification: input.justification,
      lineItems: [{description: input.item, quantity: input.quantity, unitPrice: input.unitPrice}], total: input.total};
    const initialPurchase = {...structuredClone(expectedPurchase), vendor: '', lineItems: [], [input.requiredField]: ''};
    delete initialPurchase.total;
    return {id: input.id, requiredField: input.requiredField, expectedPurchase, initialPurchase,
      quote: `Vendor: ${input.vendor}\nItem: ${input.item}\nQuantity: ${input.quantity}\nUnit price: ${input.unitPrice}\nCurrency: USD\nTotal: ${input.total}`,
      policy: input.requiredField === 'costCenter'
        ? `Every ${input.item.toLowerCase()} purchase request must include a cost center before approval.`
        : `Every ${input.item.toLowerCase()} purchase request must include a justification describing its business need before approval.`};
  });
  return {version: 'workflow-comparison-v1', fixtures,
    tasks: fixtures.flatMap((fixture, index) => MODES.map((_, offset) => ({fixtureId: fixture.id, mode: MODES[(index + offset) % 3]}))),
    maximumIntendedModelCalls: 9, sharedLifetimeBudgetUsd: '10', humanParticipants: 0,
    method: 'Agent-operated synthetic API self-test with predeclared correct purchases and rotated order',
    completionDefinition: 'Final saved draft matches all predeclared purchase fields; approval and DOCX are outside this comparison',
    correctionDefinition: 'Actual differing accepted quote fields manually replaced; planned policy-field entry is recorded separately',
    timingDefinition: 'Harness/service wall time after tenant, draft, quote ingestion, policy publication and pinning; no human reading or typing time',
    concurrentWork: 'Parent runs browser acceptance and held-out AI evaluation concurrently; timings are not isolated benchmarks',
    releaseGatePassed: false, humanVerified: false};
}

function decimal(value) {
  if (typeof value !== 'string' || !/^\d+(?:\.\d+)?$/.test(value)) return value;
  const [whole, fraction = ''] = value.split('.');
  const head = whole.replace(/^0+(?=\d)/, ''), tail = fraction.replace(/0+$/, '');
  return tail ? head + '.' + tail : head;
}

function normalized(field, value) {
  if (field === 'total') return decimal(value);
  if (field === 'lineItems' && Array.isArray(value)) return value.map(item => ({
    description: item.description, quantity: decimal(item.quantity), unitPrice: decimal(item.unitPrice)}));
  return value;
}

export function purchaseDifferences(actual, expected, fields = PURCHASE_FIELDS) {
  return fields.filter(field => JSON.stringify(normalized(field, actual[field])) !== JSON.stringify(normalized(field, expected[field])))
    .map(field => ({field, actual: actual[field] ?? null, expected: expected[field]}));
}

function writable(purchase) {
  const result = structuredClone(purchase);
  delete result.total;
  return result;
}

async function main() {
  const {values} = parseArgs({options: {live: {type: 'boolean'}, output: {type: 'string'}, 'validate-only': {type: 'boolean'}}});
  const plan = comparisonPlan();
  if (values['validate-only']) {
    console.log(JSON.stringify({plan, providerCalls: 0, qualityMeasured: false}));
    return;
  }
  if (!values.live || !values.output) throw new Error('Requires --live and --output NEW_DIRECTORY with the existing shared budget');
  const directory = resolve(values.output);
  if (existsSync(directory)) throw new Error('Output directory already exists; preserve earlier evidence');
  mkdirSync(directory, {recursive: true});
  const planBytes = encode(plan);
  writeFileSync(join(directory, 'predeclared-plan.json'), planBytes, {flag: 'wx'});
  const run = {startedAt: new Date().toISOString(), method: plan.method, planSha256: sha256(planBytes),
    codeRevision: execFileSync('git', ['rev-parse', 'HEAD'], {encoding: 'utf8'}).trim(),
    runnerSha256: sha256(readFileSync(fileURLToPath(import.meta.url))), nodeVersion: process.version,
    humanVerified: false, humanParticipants: 0, releaseGatePassed: false, concurrentWork: plan.concurrentWork,
    taskRecords: [], stoppedAI: false};
  const saveRun = () => writeFileSync(join(directory, 'run.json'), encode(run));
  saveRun();
  try {
    const token = await signIn('admin'), actor = client(token);
    for (const [index, task] of plan.tasks.entries()) {
      const fixture = plan.fixtures.find(row => row.id === task.fixtureId);
      const record = {sequence: index + 1, ...task, startedAt: new Date().toISOString(), failures: [],
        correctedQuoteFields: [], humanVerified: false, releaseGatePassed: false,
        quoteSha256: sha256(fixture.quote), policySha256: sha256(fixture.policy), completed: false, assignedWorkflowCompleted: false};
      const filename = `${String(index + 1).padStart(2, '0')}-${fixture.id}-${task.mode}.json`;
      const save = () => writeFileSync(join(directory, filename), encode(record));
      const setupStart = performance.now();
      let taskStart;
      try {
        const organization = await actor('/tenants', {method: 'POST', body: {name: `Synthetic comparison ${fixture.id} ${task.mode} ${Date.now()}`}});
        record.tenantId = organization.id;
        const tenant = `/tenants/${organization.id}`;
        let draft = await actor(`${tenant}/cases`, {method: 'POST', body: {purchase: fixture.initialPurchase}});
        record.caseId = draft.id;
        record.initialPurchase = draft.purchase;
        save();
        let policy = await uploadIndexedSource(actor, token, tenant, {kind: 'POLICY', text: fixture.policy, name: `Comparison ${fixture.id} policy`});
        policy = await actor(`${tenant}/sources/${policy.id}/publish`, {method: 'POST', body: {expectedVersion: policy.version}});
        record.policy = policy;
        record.quote = await uploadIndexedSource(actor, token, tenant, {kind: 'QUOTE', text: fixture.quote, name: `Comparison ${fixture.id} quote`, draft});
        const casePath = `${tenant}/cases/${draft.id}`, assistantPath = casePath + '/assistant';
        draft = await actor(casePath);
        record.policyPins = await actor(casePath + '/policies/refresh', {method: 'POST', body: {expectedVersion: draft.version}});
        draft = await actor(casePath);
        record.setupElapsedMs = Math.round(performance.now() - setupStart);
        record.taskStartedAt = new Date().toISOString();
        record.initialVersion = draft.version;
        taskStart = performance.now();
        save();
        const updatePurchase = async purchase => {
          draft = await actor(casePath, {method: 'PUT', body: {expectedVersion: draft.version, purchase: writable(purchase)}});
        };
        const performJob = async kind => {
          const key = kind.toLowerCase();
          if (run.stoppedAI) {record.failures.push(`${kind}: skipped after provider or budget failure`); return false;}
          record[key] = await actor(assistantPath, {method: 'POST', body: {kind, expectedVersion: draft.version,
            ...(kind === 'EXTRACTION' ? {sourceId: record.quote.id} : {})}});
          save();
          record[key] = await waitAssistantJob(actor, assistantPath, record[key]);
          save();
          if (record[key].status !== 'SUCCEEDED') {
            record.failures.push(`${kind}: ${record[key].failureCode ?? record[key].status}`);
            if (/PROVIDER|BUDGET|CONFIGURED/.test(record[key].failureCode ?? '')) run.stoppedAI = true;
            return false;
          }
          assert.deepEqual((await actor(casePath)).purchase, draft.purchase, 'AI must not automatically mutate the draft');
          return true;
        };
        if (task.mode === 'manual') {
          record.manualEnteredFields = purchaseDifferences(draft.purchase, fixture.expectedPurchase).map(row => row.field).filter(field => field !== 'total');
          await updatePurchase(fixture.expectedPurchase);
        } else {
          const extracted = await performJob('EXTRACTION');
          if (extracted) {
            const output = record.extraction.result.output;
            record.extractionDiscrepancies = purchaseDifferences(Object.fromEntries(QUOTE_FIELDS.map(field => [field, output[field]?.value])), fixture.expectedPurchase, QUOTE_FIELDS);
            record.acceptedFields = EDITABLE_QUOTE_FIELDS.filter(field => output[field]?.value != null);
            if (record.acceptedFields.length) {
              record.acceptance = await actor(`${assistantPath}/${record.extraction.jobId}/accept`, {method: 'POST',
                body: {expectedVersion: draft.version, fields: record.acceptedFields}});
              draft = await actor(casePath);
            }
            record.purchaseAfterAcceptance = draft.purchase;
            record.correctedQuoteFields = purchaseDifferences(draft.purchase, fixture.expectedPurchase, EDITABLE_QUOTE_FIELDS);
            if (record.correctedQuoteFields.length) {
              await updatePurchase({...draft.purchase, ...Object.fromEntries(EDITABLE_QUOTE_FIELDS.map(field => [field, fixture.expectedPurchase[field]]))});
            }
          } else {
            record.manualFallback = true;
            record.manualFallbackFields = EDITABLE_QUOTE_FIELDS;
            await updatePurchase({...draft.purchase, ...Object.fromEntries(EDITABLE_QUOTE_FIELDS.map(field => [field, fixture.expectedPurchase[field]]))});
          }
          if (task.mode === 'grounded-review') {
            record.purchaseBeforeReview = draft.purchase;
            if (await performJob('REVIEW')) {
              const output = record.review.result.output, evidence = record.review.result.evidence ?? {};
              record.reviewInspection = {method: 'automated-structural-inspection-not-semantic-claim-grading',
                expectedRequiredField: fixture.requiredField,
                reportedRequiredField: output.missing_information.includes(fixture.requiredField),
                findingCount: output.policy_findings.length, insufficientEvidence: output.insufficient_evidence,
                policyCited: [...output.citations, ...output.policy_findings.flatMap(finding => finding.citations)]
                  .some(citation => evidence[citation.chunkId]?.sourceId === policy.id)};
            } else record.manualFallback = true;
          }
          record.manualPolicyEntry = {field: fixture.requiredField, before: draft.purchase[fixture.requiredField], after: fixture.expectedPurchase[fixture.requiredField]};
          await updatePurchase({...draft.purchase, [fixture.requiredField]: fixture.expectedPurchase[fixture.requiredField]});
        }
        draft = await actor(casePath);
        record.finalPurchase = draft.purchase;
        record.finalVersion = draft.version;
        record.finalDifferences = purchaseDifferences(draft.purchase, fixture.expectedPurchase);
        record.completed = record.finalDifferences.length === 0;
        record.assignedWorkflowCompleted = record.completed && !record.failures.length && !record.manualFallback
          && (task.mode === 'manual' || Boolean(record.acceptance))
          && (task.mode !== 'grounded-review' || Boolean(record.reviewInspection?.reportedRequiredField && record.reviewInspection?.policyCited));
      } catch (error) {
        record.failures.push(error.message);
      }
      record.finishedAt = new Date().toISOString();
      record.taskElapsedMs = taskStart === undefined ? null : Math.round(performance.now() - taskStart);
      record.totalElapsedMs = Math.round(performance.now() - setupStart);
      save();
      run.taskRecords.push({file: filename, sha256: sha256(readFileSync(join(directory, filename))),
        fixtureId: task.fixtureId, mode: task.mode, completed: record.completed, assignedWorkflowCompleted: record.assignedWorkflowCompleted,
        taskElapsedMs: record.taskElapsedMs, correctedQuoteFieldCount: record.correctedQuoteFields.length, failureCount: record.failures.length});
      saveRun();
      console.log(`${filename}: savedCorrectDraft=${record.completed} assignedWorkflowCompleted=${record.assignedWorkflowCompleted} elapsedMs=${record.taskElapsedMs}`);
    }
  } catch (error) {
    run.failure = error.message;
  }
  run.finishedAt = new Date().toISOString();
  run.summary = MODES.map(mode => {
    const rows = run.taskRecords.filter(row => row.mode === mode);
    return {mode, intendedTasks: 3, recordedTasks: rows.length, correctDrafts: rows.filter(row => row.completed).length,
      assignedWorkflowCompletions: rows.filter(row => row.assignedWorkflowCompleted).length,
      correctedQuoteFields: rows.reduce((sum, row) => sum + row.correctedQuoteFieldCount, 0),
      taskElapsedMs: rows.map(row => row.taskElapsedMs), failureCount: rows.reduce((sum, row) => sum + row.failureCount, 0)};
  });
  const records = run.taskRecords.map(row => JSON.parse(readFileSync(join(directory, row.file), 'utf8')));
  const recordsBytes = records.map(record => JSON.stringify(record)).join('\n') + '\n';
  writeFileSync(join(directory, 'records.jsonl'), recordsBytes, {flag: 'wx'});
  run.recordsSha256 = sha256(recordsBytes);
  saveRun();
  if (run.failure || run.taskRecords.length !== 9 || run.taskRecords.some(row => !row.assignedWorkflowCompleted)) process.exitCode = 1;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await main();
