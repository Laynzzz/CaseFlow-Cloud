import { randomBytes } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';

const dir = new URL('../infrastructure/release/generated/', import.meta.url);
mkdirSync(dir, { recursive: true });
const envFile = new URL('.env', dir);
const values = existsSync(envFile) ? Object.fromEntries(readFileSync(envFile, 'utf8').trim().split(/\r?\n/).map(line => line.split('='))) : {};
for (const name of ['DB_ADMIN_PASSWORD', 'DB_MIGRATOR_PASSWORD', 'DB_API_PASSWORD', 'DB_WORKER_PASSWORD', 'S3_ACCESS_KEY', 'S3_SECRET_KEY', 'DEMO_PASSWORD', 'KEYCLOAK_ADMIN_PASSWORD']) {
  values[name] ??= randomBytes(24).toString('hex');
}
writeFileSync(envFile, Object.entries(values).map(([name, value]) => `${name}=${value}`).join('\n') + '\n', { mode: 0o600 });
const origin = 'http://127.0.0.1:18080';
const realm = {
  realm: 'caseflow', enabled: true, registrationAllowed: false, resetPasswordAllowed: false,
  sslRequired: 'none', accessTokenLifespan: 300,
  clients: [{ clientId: 'caseflow-web', name: 'CaseFlow release browser', enabled: true, publicClient: true,
    standardFlowEnabled: true, directAccessGrantsEnabled: false, redirectUris: [`${origin}/*`], webOrigins: [origin],
    attributes: { 'pkce.code.challenge.method': 'S256', 'post.logout.redirect.uris': `${origin}/*` },
    protocolMappers: [{ name: 'caseflow-api audience', protocol: 'openid-connect', protocolMapper: 'oidc-audience-mapper', config: { 'included.custom.audience': 'caseflow-api', 'access.token.claim': 'true' } }] }],
  users: ['requester', 'manager', 'finance', 'admin', 'auditor', 'outsider'].map((username, i) => ({
    id: `00000000-0000-4000-8000-${String(i + 1).padStart(12, '0')}`, username, enabled: true,
    firstName: username, lastName: 'Release', email: `${username}@caseflow.example`, emailVerified: true,
    credentials: [{ type: 'password', value: values.DEMO_PASSWORD, temporary: false }],
  })),
};
writeFileSync(new URL('caseflow-realm.json', dir), JSON.stringify(realm, null, 2) + '\n', { mode: 0o600 });
console.log('Release credentials and synthetic OIDC fixtures prepared in ignored infrastructure/release/generated. Existing credentials preserved; no live AI key copied.');
