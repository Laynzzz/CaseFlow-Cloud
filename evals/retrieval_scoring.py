"""Paired retrieval diagnostics. Missing comparisons stay in recall denominators."""
from decimal import Decimal
from scoring import rate


def compare_scores(cases,records):
    by_id={row['id']:row for row in records}
    relevant=sum(len(case['reference']['relevantPassages']) for case in cases)
    methods={name:0 for name in ('fullText','semantic','hybrid')}
    rows=[];known_cost=Decimal(0);missing=[]
    for case in cases:
        row=by_id.get(case['id'],{})
        rankings=row.get('retrievalComparisons')
        if rankings is None:missing.append(case['id'])
        targets=set(case['reference']['relevantPassages'])
        for name in methods:methods[name]+=len(targets & set((rankings or {}).get(name,[])[:5]))
        comparison=(row.get('review') or {}).get('result') or {}
        metadata=comparison.get('retrievalComparison')
        if metadata:
            if metadata['query']!=comparison.get('retrievalQuery'):raise ValueError('Comparison query differs from displayed baseline')
            known_cost+=Decimal(metadata['embeddingCostUsd'])
            rows.append(dict(id=case['id'],query=metadata['query'],corpusCount=metadata['corpusCount'],
                             fullTextElapsedMs=comparison.get('retrievalElapsedMs'),comparisonElapsedMs=metadata['elapsedMs'],
                             providerCalled=metadata['providerCalled'],embeddingCostUsd=metadata['embeddingCostUsd']))
    return dict(caseCount=len(cases),recallAt5={name:rate(value,relevant) for name,value in methods.items()},
                missingComparisonIds=missing,knownEmbeddingCostUsd=str(known_cost),cases=rows,
                releaseGatePassed=False,limitations=['Synthetic generated annotations await human verification.',
                    'One-passage corpora cannot establish a semantic advantage. Empty corpora have no recall denominator.',
                    'Timings are local component observations, not load benchmarks. Failed calls require ledger reconciliation.'])
