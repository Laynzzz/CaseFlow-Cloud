// Pure selection of frozen cases; explicit IDs support predeclared repeat subsets.
export function selectCases(splits, {split = 'development', limit, ids} = {}) {
  if (!['development', 'heldout'].includes(split)) throw new Error('Split must be development or heldout');
  const cases = splits[split];
  if (ids !== undefined) {
    if (limit !== undefined) throw new Error('Cannot combine --ids with --limit');
    const selectedIds = ids.split(',').map(id => id.trim());
    if (selectedIds.some(id => !id)) throw new Error('--ids must not contain empty entries');
    if (new Set(selectedIds).size !== selectedIds.length) throw new Error('Duplicate case ID in --ids');
    const selectedSplit = new Map(cases.map(item => [item.id, item]));
    const knownIds = new Set(Object.values(splits).flatMap(rows => rows.map(item => item.id)));
    return selectedIds.map(id => {
      if (!knownIds.has(id)) throw new Error('Unknown case ID: ' + id);
      if (!selectedSplit.has(id)) throw new Error('Case ID is outside the selected split: ' + id);
      return selectedSplit.get(id);
    });
  }
  const count = limit === undefined ? cases.length : Number(limit);
  if (!Number.isInteger(count) || count < 1 || count > cases.length) {
    throw new Error('Limit must be a positive count within this split');
  }
  return cases.slice(0, count);
}
