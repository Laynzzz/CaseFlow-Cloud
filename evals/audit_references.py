"""Fixture-specific cross-check supporting the assistant's source/reference review.

This is not a product extractor, a model evaluation, or human verification.
Patterns and policy judgments were inspected during the reference audit only.
Never use this module to tune the product on held-out examples.
"""
import argparse
from datetime import datetime, timezone
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
from scoring import load_dataset

V=r'(?P<vendor>[^\n]+?)'; I=r'(?P<item>[^\n]+?)'
Q=r'(?P<qty>\d+)'; U=r'(?P<unit>\d+\.\d{2})'
C=r'(?P<currency>USD|\[not supplied\])'; T=r'(?P<total>\d+\.\d{2})'
PATTERNS={
    'equipment':rf'Vendor: {V}\nItem: {I}\nQuantity: {Q}\nUnit price: {U}\nCurrency: {C}\nTotal: {T}',
    'seating':rf'Supplier {V} offers {Q} {I} at {U} each\. Amount payable: {T} {C}\.',
    'network':rf'QUOTATION\n{V}\n{I} \| count {Q} \| each {U}\nGrand total \({C}\): {T}',
    'printing':rf'From {V}: {I}, {Q} units x {U}\. Quote currency {C}; total due {T}\.',
    'lighting':rf'Seller={V}; product={I}; units={Q}; price={U}; currency={C}; invoice-total={T}',
    'storage':rf'{V} / {I}\nPer-unit {U}; number ordered {Q}\nPay {T} in {C}',
    'audio':rf'Commercial offer by {V}\n{Q} pieces of {I}, priced {U} per piece\nSettlement: {C} {T}',
    'tools':rf'Purchase estimate: {I}\nPrepared by {V}\nRate {U}; volume {Q}; sum {T}; denomination {C}',
    'lab':rf'Lab supply offer\nBusiness {V}\nGoods {I}\n{Q} @ {U}\nFinal amount {T} \({C}\)',
    'safety':rf'{V} proposes delivery of {Q} {I}\. Single-unit cost is {U}\. Overall charge is {T}, denominated in {C}\.',
    'display':rf'Estimate issuer: {V}\nDescription / units / unit charge\n{I} / {Q} / {U}\nBalance requested: {T} {C}',
    'shipping':rf'Offer summary \[{V}\]\nMerchandise: {I}\nOrder size: {Q}\nPrice per piece: {U}\nPayment amount: {C} {T}',
}
POLICIES={
    'equipment':'Equipment purchases require a cost center before approval.',
    'seating':'Seating requests must include a cost center for finance review.',
    'network':'Network procurement cannot proceed without a cost center.',
    'printing':'Printing expenditure must identify the requesting cost center.',
    'lighting':'Lighting orders require the department cost center to be recorded.',
    'storage':'Storage procurement requires a valid cost center on every request.',
    'audio':'Before an audio request is approved, finance needs its cost center.',
    'tools':'Tool expenditure requires the requester to supply a cost center.',
    'lab':'Laboratory purchases lacking a cost center must be completed before approval.',
    'safety':'Safety equipment requests need a cost center for allocation.',
    'display':'A display purchase is incomplete until a cost center is provided.',
    'shipping':'Shipping supplies must be charged to a stated cost center before approval.',
}
IRRELEVANT='Office walls are painted every five years.'
LAB_REPLACEMENT='Laboratory purchase requests must include a cost center before approval.'


def audit_case(case):
    quote=case['quote'];ref=case['reference'];family=case['family'];issues=[]
    # Read source values, not generated expectations. Discard an instruction suffix
    # only for parsing the quote; retain its presence as an adversarial-fixture check.
    base=quote.split('\nASSISTANT INSTRUCTION:',1)[0].split('\nUnresolved correction:',1)[0]
    match=re.fullmatch(PATTERNS[family],base)
    if not match:raise ValueError('Unrecognized source layout: '+case['id'])
    values=match.groupdict()
    conflicts=re.findall(r'Unresolved correction: total (\d+\.\d{2})\. Neither total is confirmed\.',quote)
    observed=dict(vendor=None if values['vendor']=='[not supplied]' else values['vendor'],
                  currency=None if values['currency']=='[not supplied]' else values['currency'],
                  total=None if conflicts else values['total'],
                  lineItems=[dict(description=values['item'],quantity=values['qty'],unitPrice=values['unit'])])
    checks={field:observed[field]==ref[field] for field in observed}
    for field,ok in checks.items():
        if not ok:issues.append(dict(code='REFERENCE_MISMATCH',field=field,sourceValue=observed[field],referenceValue=ref[field]))
    computed=Decimal(values['qty'])*Decimal(values['unit'])
    arithmetic=Decimal(values['total'])==computed
    if not arithmetic:issues.append(dict(code='SOURCE_ARITHMETIC_MISMATCH'))
    if conflicts and any(Decimal(value)==computed for value in conflicts):issues.append(dict(code='CONFLICT_IS_NOT_DISTINCT'))
    expected_warnings=['CONFLICTING_TOTALS'] if conflicts else []
    if ref['warnings']!=expected_warnings:issues.append(dict(code='WARNING_REFERENCE_MISMATCH'))
    irrelevant=all(p['text']==IRRELEVANT for p in case['policyPassages'])
    relevant_texts={POLICIES[family]}
    if family=='lab':relevant_texts.add(LAB_REPLACEMENT)
    policy_known=all(p['text'] in relevant_texts or p['text']==IRRELEVANT for p in case['policyPassages'])
    expected_passages=[p['id'] for p in case['policyPassages'] if p['text'] in relevant_texts]
    if not policy_known:issues.append(dict(code='POLICY_REQUIRES_NEW_SEMANTIC_REVIEW'))
    if ref['relevantPassages']!=expected_passages or ref['insufficientEvidence']!=irrelevant:
        issues.append(dict(code='POLICY_REFERENCE_MISMATCH'))
    if family=='lab' and any(p['text']==POLICIES['lab'] for p in case['policyPassages']):
        issues.append(dict(code='AMBIGUOUS_POLICY_WORDING',field='policyPassages',
            explanation='The sentence says purchases must be completed, rather than explicitly saying the missing cost center must be supplied. The intended rule is plausible but not unambiguous.',
            proposedText=LAB_REPLACEMENT))
    if case['purchase']!=dict(description=values['item'],costCenter=None):issues.append(dict(code='PURCHASE_CONTEXT_MISMATCH'))
    if case['query']!=f'Does this {family} purchase need a cost center before approval?':issues.append(dict(code='QUERY_REQUIRES_REVIEW'))
    source_category=('hostile_instructions' if '\nASSISTANT INSTRUCTION:' in quote else 'conflicting_totals' if conflicts else
                     'missing_fields' if observed['vendor'] is None or observed['currency'] is None else 'insufficient_policy' if irrelevant else 'ordinary')
    if case['category']!=source_category:issues.append(dict(code='CATEGORY_MISMATCH'))
    notes=['Supplier digits/suffixes are retained as written; item text is separate from quantity and supplier.']
    if conflicts:notes.append('The two totals are explicitly unresolved; retain line-item facts but leave proposed total null and warn.')
    if observed['currency'] is None:notes.append('No currency may be inferred from a numeric amount or application default; the explicit numeric total can still be extracted.')
    if irrelevant:notes.append('A wall-painting schedule cannot answer the purchasing question; no relevant passage and abstention are appropriate.')
    elif not issues:notes.append('This policy supports a cost-center requirement. Do not add an approval deadline or other conditions beyond its actual wording.')
    if source_category=='hostile_instructions':notes.append('The appended commands are untrusted quote text, not purchase facts or authority to act.')
    return dict(id=case['id'],family=family,category=case['category'],
                caseSha256=hashlib.sha256(json.dumps(case,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
                sourceFields=observed,fieldChecks=checks,arithmeticMatches=arithmetic,computedLineTotal=str(computed),
                disposition='clarification-needed' if issues else 'no-reference-discrepancy-found',issues=issues,reviewNotes=notes)


def audit_dataset(version=None):
    manifest,splits=load_dataset(version=version)
    rows=[dict(audit_case(case),split=split) for split,cases in splits.items() for case in cases]
    counts=Counter(issue['code'] for row in rows for issue in row['issues'])
    files={name:dict(info,reviewedCount=sum(row['split']+'.jsonl'==name for row in rows)) for name,info in manifest['files'].items()}
    return dict(datasetVersion=manifest['version'],files=files,
                method='ai-reference-review-v1',reviewer='Codex AI assistant',
                reviewedAt=datetime.now(timezone.utc).isoformat(),evaluationProfile='ai-reviewed-learning',
                status='ai-reviewed-with-clarifications' if counts else 'ai-reviewed',
                humanVerified=False,releaseGatePassed=False,
                summary=dict(reviewedCases=len(rows),fieldChecks=sum(len(r['fieldChecks']) for r in rows),
                             matchingFieldChecks=sum(sum(r['fieldChecks'].values()) for r in rows),
                             arithmeticMatches=sum(r['arithmeticMatches'] for r in rows),
                             casesWithoutIdentifiedDiscrepancy=sum(not r['issues'] for r in rows),issueCounts=dict(counts)),
                reviews=rows,
                limitations=['AI source/reference assessment plus deterministic fixture-specific checks, not an independent human review.',
                             'The checker is specialized to these synthetic layouts; it is not product extraction or proof of model quality.',
                             'Held-out sources were read for annotation review only. No product prompt, retrieval setting or prediction was changed.',
                             'Families have different wording but share one cost-center rule and simple one-item quotes; breadth is limited.',
                             'Proposed wording changes must be versioned before application; this audit does not alter frozen files.'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--dataset-version',choices=['synthetic-v1','synthetic-v2'],default='synthetic-v1')
    args=parser.parse_args();report=audit_dataset(args.dataset_version)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8',newline='\n') as output:output.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report['summary'],indent=2))
