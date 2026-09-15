import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {join} from 'node:path';

export function loadFrozenDataset(directory) {
  const manifest=JSON.parse(readFileSync(join(directory,'manifest.json'),'utf8'));
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

export function requireAnnotationReview(manifest, review) {
  if(!review || review.status!=='verified' || review.datasetVersion!==manifest.version ||
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
