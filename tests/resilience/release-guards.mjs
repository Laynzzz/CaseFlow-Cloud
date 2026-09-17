export function ownedDependency(container, service) {
  if (!['postgres', 'kafka'].includes(service)) throw new Error('Only release database/broker faults are allowed');
  if (!/^[a-f0-9]{64}$/.test(container.Id ?? '')) throw new Error('Exact container ID required');
  const labels = container.Config?.Labels ?? {};
  if (labels['com.docker.compose.project'] !== 'caseflow-release' || labels['com.docker.compose.service'] !== service)
    throw new Error('Container is outside the isolated release project');
  return container.Id;
}
