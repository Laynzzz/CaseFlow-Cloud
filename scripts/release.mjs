import { execFileSync, spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { readdirSync } from 'node:fs';

const root = fileURLToPath(new URL('../', import.meta.url));
const dir = fileURLToPath(new URL('../infrastructure/release/generated/', import.meta.url));
mkdirSync(dir, { recursive: true });
const arguments_ = process.argv.slice(2);
const [command, name] = arguments_.filter(value => value !== '--observability');
const observability = arguments_.includes('--observability');
const json = file => JSON.parse(readFileSync(file, 'utf8'));
const save = (file, data) => writeFileSync(file, JSON.stringify(data, null, 2) + '\n');
function run(program, args, options = {}) {
  const result = spawnSync(program, args, { cwd: root, stdio: 'inherit', ...options });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`${program} ${args[0]} failed (${result.status})`);
}
const capture = (program, args) => execFileSync(program, args, { cwd: root, encoding: 'utf8' }).trim();
function sourceDigest() {
  const files = [];
  function walk(path) {
    for (const entry of readdirSync(`${root}/${path}`, { withFileTypes: true })) {
      if (['node_modules', 'build', 'dist', '.gradle', '.venv', '__pycache__', '.pytest_cache', 'generated'].includes(entry.name) || entry.name.endsWith('.log') || entry.name.startsWith('.env')) continue;
      const next = `${path}/${entry.name}`;
      if (entry.isDirectory()) walk(next); else if (entry.isFile()) files.push(next);
    }
  }
  for (const path of ['apps/web', 'services/case-api', 'services/worker', 'db/migrations', 'contracts']) walk(path);
  files.push('.dockerignore', 'infrastructure/release/HealthProbe.java');
  const hash = createHash('sha256');
  for (const path of files.sort()) hash.update(path).update('\0').update(readFileSync(`${root}/${path}`)).update('\0');
  return hash.digest('hex');
}
function manifestPath(value) {
  if (!/^[a-z0-9][a-z0-9-]{0,63}$/.test(value ?? '')) throw new Error('Specify a release name using lowercase letters, digits and hyphens (maximum 64 characters).');
  return `${dir}/${value}.json`;
}
function compose(manifest, args) {
  for (const image of [manifest.api, manifest.worker]) {
    if (!/^sha256:[a-f0-9]{64}$/.test(image)) throw new Error('Release manifest must contain immutable local image IDs.');
    capture('docker', ['image', 'inspect', image, '--format', '{{.Id}}']);
  }
  run('docker', ['compose', '--project-name', 'caseflow-release', '--env-file', `${dir}/.env`, '-f', 'compose.release.yaml', ...(manifest.observability ? ['-f', 'compose.observability.yaml'] : []), ...args], {
    env: { ...process.env, RELEASE_API_IMAGE: manifest.api, RELEASE_WORKER_IMAGE: manifest.worker },
  });
}
if (command === 'build') {
  const path = manifestPath(name);
  if (existsSync(path)) throw new Error('Release manifest already exists; choose a new name.');
  if (!existsSync(`${dir}/.env`)) run(process.execPath, ['scripts/init-release.mjs']);
  const revision = capture('git', ['rev-parse', 'HEAD']);
  const dirty = capture('git', ['status', '--porcelain']).length > 0;
  const sourceSha256 = sourceDigest();
  for (const service of ['worker', 'case-api']) {
    run('docker', ['build', '--file', `services/${service}/Dockerfile`, '--build-arg', `REVISION=${revision}`, '--label', `dev.caseflow.release=${name}`, '--tag', `caseflow/${service}:${name}`, '.']);
  }
  if (sourceDigest() !== sourceSha256) throw new Error('Source inputs changed during image builds; choose a new release name and rebuild from stable inputs.');
  const result = { name, revision, dirty, sourceSha256, createdAt: new Date().toISOString(),
    api: capture('docker', ['image', 'inspect', `caseflow/case-api:${name}`, '--format', '{{.Id}}']),
    worker: capture('docker', ['image', 'inspect', `caseflow/worker:${name}`, '--format', '{{.Id}}']) };
  save(path, result);
  console.log(`Built immutable image manifest: infrastructure/release/generated/${name}.json`);
} else if (command === 'deploy' || command === 'rollback') {
  const manifest = json(command === 'rollback' ? `${dir}/previous.json` : manifestPath(name));
  if (command === 'deploy') manifest.observability = observability;
  const previous = existsSync(`${dir}/current.json`) ? json(`${dir}/current.json`) : null;
  // Flyway applies forward migrations on API startup. Rollback never undoes schema/data.
  compose(manifest, ['up', '-d', '--wait', '--wait-timeout', '240']);
  run(process.execPath, ['scripts/smoke-release.mjs']);
  if (previous) save(`${dir}/previous.json`, previous);
  save(`${dir}/current.json`, manifest);
  console.log(`PASS ${command}: ${manifest.name}; immutable API ${manifest.api}, worker ${manifest.worker}`);
} else if (command === 'status' || command === 'stop') {
  compose(json(`${dir}/current.json`), command === 'status' ? ['ps'] : ['stop']);
} else {
  throw new Error('Usage: node scripts/release.mjs build <name> | deploy <name> | rollback | status | stop');
}
