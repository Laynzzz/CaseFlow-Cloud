import { randomBytes } from 'node:crypto';
import { writeFileSync, existsSync, readFileSync, appendFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const file = fileURLToPath(new URL('../.env', import.meta.url));
if (existsSync(file)) {
  console.log('Existing .env preserved.');
} else {
  const keys = ['DB_ADMIN_PASSWORD', 'DB_MIGRATOR_PASSWORD', 'DB_API_PASSWORD', 'DB_WORKER_PASSWORD'];
  writeFileSync(file, keys.map(key => `${key}=${randomBytes(24).toString('hex')}`).join('\n') + '\n', { flag: 'wx', mode: 0o600 });
  console.log('Created ignored .env with random local database passwords. Do not commit it.');
}
const current = readFileSync(file, 'utf8');
for (const key of ['S3_ACCESS_KEY', 'S3_SECRET_KEY']) {
  if (!new RegExp(`^${key}=`, 'm').test(current)) appendFileSync(file, `${key}=${randomBytes(24).toString('hex')}\n`);
}
