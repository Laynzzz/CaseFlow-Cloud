// Recheck the recorded AI judgments. This validates evidence; it does not perform a new semantic review.
// Run from the repository root. Fixture-specific parsers are deliberately not product extraction code.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {loadFrozenDataset,requireAnnotationReview} from '../../../../evals/dataset.mjs';

const sha=v=>createHash('sha256').update(v).digest('hex');
const audit=JSON.parse(readFileSync(new URL('./audit.json',import.meta.url),'utf8'));
const current=loadFrozenDataset('evals','synthetic-v3');
const old=loadFrozenDataset('evals','synthetic-v2');
const oldBytes=readFileSync(audit.carryForward.sourceAudit);
const oldAudit=JSON.parse(oldBytes);
requireAnnotationReview(old.manifest,oldAudit,'ai-reviewed-learning',old.splits);
requireAnnotationReview(current.manifest,audit,'ai-reviewed-learning',current.splits);
assert.equal(current.manifest.files['heldout.jsonl'].sha256,'4897f4d248cac923945e0a6fa4d34a8a6a21bf4ce7809a4dc1803014cec1fe54');
assert.equal(current.manifest.files['development.jsonl'].sha256,'731f453164ba4eb437b89ea245780aefb60bacad12a00ec90c090d835307c318');
assert.equal(sha(oldBytes),audit.carryForward.sourceAuditSha256);
assert.deepEqual(readFileSync('evals/datasets/synthetic-v3/development.jsonl'),Buffer.concat(['development','heldout'].map(s=>readFileSync(`evals/datasets/synthetic-v2/${s}.jsonl`))));
const judgments=new Map(audit.reviews.map(r=>[r.id,r]));
const oldCases=new Map(Object.entries(old.splits).flatMap(([split,cases])=>cases.map(c=>[c.id,{split,c}])));
for(const oldJudgment of oldAudit.reviews){
  const currentJudgment=judgments.get(oldJudgment.id);
  const {provenance,...carried}=currentJudgment;
  assert.deepEqual({...carried,split:provenance.sourceSplit},oldJudgment);
  assert.equal(currentJudgment.split,'development');
  assert.equal(provenance.sourceCaseSha256,oldJudgment.caseSha256);
  assert.equal(provenance.sourceSplit,oldCases.get(oldJudgment.id).split);
  assert.equal(provenance.sourceAuditSha256,sha(oldBytes));
  assert.equal(provenance.sourceReviewer,oldAudit.reviewer);
  assert.equal(provenance.sourceReviewedAt,oldAudit.reviewedAt);
  assert.deepEqual(current.splits.development.find(c=>c.id===oldJudgment.id),oldCases.get(oldJudgment.id).c);
}

const moneyCents=value=>{
  assert.match(value,/^\d+\.\d{2}$/);
  return BigInt(value.replace('.',''));
};
const amount=cents=>`${cents/100n}.${String(cents%100n).padStart(2,'0')}`;
const nullable=v=>v==='[not supplied]'?null:v;
function sourceFields(c){
  const q=c.quote, get=regex=>{const m=q.match(regex);assert.ok(m,c.id+' source layout');return m[1];};
  let vendor,currency,description,quantity,unitPrice,total;
  switch(c.layout){
    case 'markdown-table': {
      vendor=get(/^Issued by: (.+)$/m);currency=get(/^All prices use currency code: (.+)$/m);
      const row=q.match(/^\| (.+) \| (\d+) \| (\d+\.\d{2}) \| (\d+\.\d{2}) \|$/m);
      assert.ok(row); [,description,quantity,unitPrice]=row;
      total=get(/^Amount payable for this offer: (\d+\.\d{2})$/m);assert.equal(row[4],total);
      break;
    }
    case 'xml-offer':
      vendor=get(/<supplier>(.*?)<\/supplier>/);currency=get(/<currencyCode>(.*?)<\/currencyCode>/);
      description=get(/<description>(.*?)<\/description>/);quantity=get(/<quantity>(.*?)<\/quantity>/);
      unitPrice=get(/<unitPrice>(.*?)<\/unitPrice>/);total=get(/<amountPayable>(.*?)<\/amountPayable>/);break;
    case 'json-offer': {
      const start=q.indexOf('\n{')+1, end=q.indexOf('\n}',start)+2;
      const data=JSON.parse(q.slice(start,end));assert.equal(data.goods.length,1);
      vendor=data.supplier;currency=data.currencyCode;({description,quantity,unitPrice}=data.goods[0]);total=data.amountPayable;break;
    }
    case 'csv-matrix': {
      const lines=q.split('\n');assert.equal(lines[1],'supplier,currencyCode,product,quantity,unitPrice,amountPayable');
      const cells=lines[2].split(',').map(x=>x.replace(/^"|"$/g,''));assert.equal(cells.length,6);
      [vendor,currency,description,quantity,unitPrice,total]=cells;break;
    }
    case 'nested-proposal':
      vendor=get(/^  \* Seller: (.+)$/m);currency=get(/^  \* Currency code: (.+)$/m);
      description=get(/^  \* Product: (.+)$/m);quantity=get(/^  \* Units ordered: (.+)$/m);
      unitPrice=get(/^  \* Price for one unit: (.+)$/m);total=get(/^  \* Full amount payable: (.+)$/m);break;
    case 'offer-interview': {
      const answers=[...q.matchAll(/^Supplier: (.+)$/gm)].map(m=>m[1]);assert.equal(answers.length,5);
      [vendor,,unitPrice,currency,total]=answers;const item=answers[1].match(/^(\d+) units of (.+)\.$/);assert.ok(item);
      [,quantity,description]=item;break;
    }
    default: throw new Error('Unaudited layout '+c.layout);
  }
  return {vendor:nullable(vendor),currency:nullable(currency),total,lineItems:[{description,quantity,unitPrice}]};
}
let arithmetic=0, fields=0, policyReviews=0, abstentions=0, conflicts=0;
for(const c of current.splits.heldout){
  const r=judgments.get(c.id), source=sourceFields(c), item=source.lineItems[0];
  const calculated=amount(moneyCents(item.unitPrice)*BigInt(item.quantity));
  assert.equal(calculated,source.total,c.id+' arithmetic');assert.equal(calculated,r.computedLineTotal);arithmetic++;
  const alternate=c.quote.match(/alternative amount payable is (\d+\.\d{2})\./)?.[1];
  assert.deepEqual(r.sourcePayableAmounts,alternate?[source.total,alternate]:[source.total]);
  if(alternate){assert.ok(c.quote.includes('neither supersedes the other'));assert.notEqual(alternate,source.total);source.total=null;conflicts++;}
  assert.deepEqual(source,r.sourceFields);for(const [key,value]of Object.entries(source)){assert.deepEqual(value,c.reference[key]);fields++;}
  assert.deepEqual(c.reference.warnings,alternate?['CONFLICTING_TOTALS']:[]);
  const irrelevant=c.policyPassages[0].text==='The office garden watering schedule is posted beside the courtyard entrance.';
  const expectedCategory=alternate?'conflicting_totals':source.vendor===null?'missing_fields':irrelevant?'insufficient_policy':c.quote.includes('ASSISTANT INSTRUCTION:')?'hostile_instructions':'ordinary';
  assert.equal(c.category,expectedCategory);assert.equal(r.categoryMatches,true);assert.equal(r.warningsMatch,true);
  assert.equal(r.policyReview.passageText,c.policyPassages[0].text);
  assert.equal(r.policyReview.passageId,c.policyPassages[0].id);
  assert.deepEqual(r.policyReview.referenceRelevantPassages,irrelevant?[]:[c.policyPassages[0].id]);
  assert.deepEqual(c.reference.relevantPassages,r.policyReview.referenceRelevantPassages);
  assert.equal(r.policyReview.expectedInsufficientEvidence,irrelevant);assert.equal(c.reference.insufficientEvidence,irrelevant);
  assert.equal(r.policyReview.requiredPurchaseField,c.requiredPurchaseField);assert.equal(c.purchase[c.requiredPurchaseField],null);
  assert.equal(r.provenance.kind,'new-ai-source-review');assert.ok(r.reviewNotes.some(n=>n.includes(c.id)));
  policyReviews++;if(irrelevant)abstentions++;
}
assert.equal(fields,240);assert.equal(arithmetic,60);assert.equal(policyReviews,60);assert.equal(abstentions,12);assert.equal(conflicts,12);
assert.equal(audit.summary.newSourceReviews,60);assert.equal(audit.summary.carriedForwardExactCaseReviews,120);
console.log(JSON.stringify({status:'passed',annotationReviewContract:true,exactCarriedForwardCases:120,newSourceFields:fields,newArithmeticChecks:arithmetic,newPolicyReviews:policyReviews,newPolicyAbstentions:abstentions,newConflictingTotals:conflicts,discrepancies:0,paidProviderCalls:0},null,2));
