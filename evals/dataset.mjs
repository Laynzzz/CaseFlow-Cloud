import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {join} from 'node:path';

export function loadFrozenDataset(directory, version='synthetic-v1') {
  if(!['synthetic-v1','synthetic-v2','synthetic-v3'].includes(version)) throw new Error('Unknown frozen dataset version');
  if(version!=='synthetic-v1') directory=join(directory,'datasets',version);
  const manifest=JSON.parse(readFileSync(join(directory,'manifest.json'),'utf8'));
  if(manifest.version!==version) throw new Error('Dataset version does not match its manifest');
  const splits={}, ids=new Set();
  for(const split of ['development','heldout']) {
    const name=split+'.jsonl', bytes=readFileSync(join(directory,name));
    if(createHash('sha256').update(bytes).digest('hex')!==manifest.files[name].sha256) throw new Error('Dataset checksum changed: '+name);
    const rows=bytes.toString('utf8').trim().split(/\r?\n/).map(line=>JSON.parse(line));
    if(rows.length!==manifest.files[name].count) throw new Error('Dataset count changed: '+name);
    for(const row of rows) {
      if(ids.has(row.id)) throw new Error('Duplicate dataset ID');
      ids.add(row.id);
      const passages=new Set(row.policyPassages.map(p=>p.id));
      if(!row.reference.relevantPassages.every(id=>passages.has(id))) throw new Error('Reference passage is absent');
    }
    const families=[...new Set(rows.map(r=>r.family))].sort();
    if(JSON.stringify(families)!==JSON.stringify(manifest.files[name].families)) throw new Error('Dataset family list changed');
    splits[split]=rows;
  }
  const development=new Set(splits.development.map(r=>r.family));
  if(splits.heldout.some(r=>development.has(r.family))) throw new Error('Development and held-out families overlap');
  return {manifest,splits};
}

export function requireAnnotationReview(manifest, review, profile='human-reviewed', splits=null) {
  if(!['human-reviewed','ai-reviewed-learning'].includes(profile)) throw new Error('Unknown evaluation profile');
  if(profile==='ai-reviewed-learning') {
    if(!review || review.method!=='ai-reference-review-v1' || review.status!=='ai-reviewed' ||
       review.evaluationProfile!==profile || review.humanVerified!==false || review.releaseGatePassed!==false ||
       review.datasetVersion!==manifest.version || typeof review.reviewer!=='string' || !review.reviewer.trim() ||
       !Number.isFinite(Date.parse(review.reviewedAt)) || !splits || !Array.isArray(review.reviews)) {
      throw new Error('Learning profile requires a complete, explicitly AI reference review');
    }
    const expected=new Map(Object.entries(splits).flatMap(([split,cases])=>cases.map(c=>[c.id,{split,case:c}])));
    const seen=new Set();
    for(const row of review.reviews) {
      const item=expected.get(row.id);
      if(!item || seen.has(row.id) || row.split!==item.split || row.caseSha256!==caseHash(item.case) ||
         !Array.isArray(row.issues) || row.issues.length || row.disposition!=='no-reference-discrepancy-found' ||
         !['vendor','currency','total','lineItems'].every(field=>row.fieldChecks?.[field]===true) ||
         row.arithmeticMatches!==true || !Array.isArray(row.reviewNotes) || !row.reviewNotes.length) {
        throw new Error('AI reference review has stale, unresolved or duplicate case judgments');
      }
      seen.add(row.id);
    }
    if(seen.size!==expected.size) throw new Error('AI reference review must cover every frozen case');
  } else if(!review || review.status!=='verified' || review.datasetVersion!==manifest.version ||
     !review.reviewer?.trim() || !review.reviewedAt || review.method!=='human-reference-review') {
    throw new Error('Held-out execution requires a recorded human reference review');
  }
  for(const split of ['development','heldout']) {
    const name=split+'.jsonl';
    if(review.files?.[name]?.sha256!==manifest.files[name].sha256 || review.files[name].reviewedCount!==manifest.files[name].count) {
      throw new Error('Annotation review must cover the exact frozen files and all rows');
    }
  }
}

// Match the audit's recursively sorted, compact JSON for these ASCII fixtures.
function caseHash(value) {
  const canonical=v=>Array.isArray(v)?v.map(canonical):v && typeof v==='object'
    ?Object.fromEntries(Object.keys(v).sort().map(key=>[key,canonical(v[key])])):v;
  return createHash('sha256').update(JSON.stringify(canonical(value))).digest('hex');
}
