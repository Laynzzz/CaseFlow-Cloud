"""Create a local, offline human reference-review packet; never marks references reviewed."""
import argparse
import html
import json
from pathlib import Path
from scoring import load_dataset

if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    manifest,splits=load_dataset()
    data=dict(manifest=manifest,cases=[dict(row,split=split) for split,rows in splits.items() for row in rows])
    encoded=html.escape(json.dumps(data,ensure_ascii=True),quote=False)
    page=r'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CaseFlow reference review</title>
<style>body{font:17px system-ui;margin:2rem auto;max-width:1000px;padding:0 1rem;color:#1d2d3d;background:#f6f8fa}h1{font-size:2rem}section{background:white;border:1px solid #ccd5df;border-radius:12px;padding:1.2rem;margin:1rem 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:15px/1.6 system-ui}button,select,input,textarea{font:inherit;padding:.6rem;margin:.3rem 0}button{cursor:pointer}label{display:block}textarea{width:95%;min-height:4rem}.row{display:flex;gap:1rem;flex-wrap:wrap}.muted{color:#536579}#progress{font-weight:bold}button:disabled{cursor:default;opacity:.5}</style>
<h1>Check the synthetic reference answers</h1>
<p>Compare each quote and policy with its expected answers. Check the vendor, currency, total, items, relevant passages and whether policy evidence is absent. Missing or conflicting values should remain empty. These are expected answers for later testing, not AI results.</p>
<p class="muted">This page works offline and sends nothing to a server. Mark an item only after you have checked it. Save a progress file before closing; you can import it to continue. A correction blocks verification until the dataset is corrected and a new packet is generated.</p>
<section><label>Your name or reviewer identifier <input id="reviewer" autocomplete="off"></label><div class="row"><button id="save">Download review / progress</button><label>Resume saved progress <input id="import" type="file" accept="application/json"></label></div><p id="progress" role="status"></p><p id="message" role="alert"></p></section>
<section><label>Case <select id="case"></select></label><div class="row"><button id="previous">Previous</button><button id="next">Next</button></div><h2 id="title"></h2><h3>Quote</h3><pre id="quote"></pre><h3>Purchase facts and question</h3><pre id="purchase"></pre><h3>Policy passages</h3><pre id="policies"></pre><h3>Expected answers</h3><pre id="reference"></pre><label><input id="checked" type="checkbox"> I checked this source and its reference answers</label><label>Correction needed (leave empty if correct)<textarea id="correction"></textarea></label></section>
<pre id="data" hidden>DATA</pre>
<script>
const data=JSON.parse(document.getElementById('data').textContent), cases=data.cases, byId=new Map(cases.map(c=>[c.id,c]));
const $=id=>document.getElementById(id), reviews={}; let index=0;
for(const c of cases){const option=document.createElement('option');option.value=c.id;option.textContent=c.split+' · '+c.id+' · '+c.category;$('case').append(option);}
function counts(){return cases.filter(c=>reviews[c.id]?.checked && !reviews[c.id]?.correction.trim()).length;}
function render(){const c=cases[index], review=reviews[c.id]??{checked:false,correction:''};$('case').value=c.id;$('title').textContent=c.id+' · '+c.category;$('quote').textContent=c.quote;$('purchase').textContent=JSON.stringify(c.purchase,null,2)+'\n'+c.query;$('policies').textContent=c.policyPassages.length?c.policyPassages.map(p=>p.id+'\n'+p.text).join('\n\n'):'No policy evidence supplied.';$('reference').textContent=JSON.stringify(c.reference,null,2);$('checked').checked=review.checked;$('correction').value=review.correction;$('progress').textContent=counts()+' / '+cases.length+' checked without corrections';$('previous').disabled=index===0;$('next').disabled=index===cases.length-1;}
function remember(){reviews[cases[index].id]={checked:$('checked').checked,correction:$('correction').value};$('progress').textContent=counts()+' / '+cases.length+' checked without corrections';}
$('case').onchange=()=>{index=cases.findIndex(c=>c.id===$('case').value);render();};$('previous').onclick=()=>{index--;render();};$('next').onclick=()=>{index++;render();};$('checked').onchange=remember;$('correction').oninput=remember;
$('save').onclick=()=>{const reviewer=$('reviewer').value.trim();if(!reviewer){$('message').textContent='Enter the actual reviewer identifier before saving.';return;}const files={};for(const split of ['development','heldout']){const name=split+'.jsonl';files[name]={sha256:data.manifest.files[name].sha256,reviewedCount:cases.filter(c=>c.split===split && reviews[c.id]?.checked && !reviews[c.id].correction.trim()).length};}const report={status:counts()===cases.length?'verified':'incomplete',method:'human-reference-review',datasetVersion:data.manifest.version,reviewer,reviewedAt:new Date().toISOString(),files,reviews};const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='caseflow-reference-review.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);$('message').textContent=report.status==='verified'?'Review saved. Return this file for the held-out run.':'Incomplete progress saved; this does not authorize held-out execution.';};
$('import').onchange=async()=>{try{const report=JSON.parse(await $('import').files[0].text());if(report.datasetVersion!==data.manifest.version||['development.jsonl','heldout.jsonl'].some(name=>report.files?.[name]?.sha256!==data.manifest.files[name].sha256))throw Error('Saved review does not match these frozen sources.');for(const [id,r] of Object.entries(report.reviews??{})){if(!byId.has(id)||typeof r.checked!=='boolean'||typeof r.correction!=='string')throw Error('Invalid review entry.');}Object.keys(reviews).forEach(id=>delete reviews[id]);Object.assign(reviews,report.reviews);$('reviewer').value=report.reviewer??'';render();$('message').textContent='Progress restored.';}catch(e){$('message').textContent=e.message;}};
render();
</script></html>'''
    # Escape embedded data separately; never interpolate source text into executable JavaScript.
    page=page.replace('>DATA</pre>','>'+encoded+'</pre>')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open("x",encoding="utf-8") as output:output.write(page)
    print(f"Created {args.output}; 120 unchecked cases, no provider calls or review claims.")
