// Cross-platform local/CI gates. Only generated synthetic environment files are loaded.
import {spawnSync, execFileSync} from 'node:child_process';
import {createHash, randomBytes} from 'node:crypto';
import {copyFileSync, existsSync, mkdirSync, readFileSync, writeFileSync, readdirSync, unlinkSync} from 'node:fs';
import {dirname, resolve, relative, sep} from 'node:path';
import {fileURLToPath} from 'node:url';

const root=resolve(dirname(fileURLToPath(import.meta.url)), '..');
const args=process.argv.slice(2), command=args[0];
const option=(name,fallback)=>args.includes(name)?args[args.indexOf(name)+1]:fallback;
const output=resolve(root,option('--output','output/ci'));
mkdirSync(output,{recursive:true});
const envFile=resolve(root,option('--env-file','.env.ci'));
const env={...process.env,PYTHONPATH:resolve(root,'services/worker'),OTEL_TRACES_EXPORTER:'none',OTEL_EXPORTER_OTLP_ENDPOINT:'',CASEFLOW_TRACING_EXPORT_ENABLED:'false'};
for(const key of ['OPENAI_API_KEY','ANTHROPIC_API_KEY','AWS_ACCESS_KEY_ID','AWS_SECRET_ACCESS_KEY','AWS_SESSION_TOKEN']) delete env[key];
if(existsSync(envFile)) for(const line of readFileSync(envFile,'utf8').split(/\r?\n/)) {
  const match=/^([A-Z][A-Z0-9_]*)=([^\r\n]*)$/.exec(line);
  if(match) env[match[1]]=match[2];
}
for(const key of ['OPENAI_API_KEY','ANTHROPIC_API_KEY','AWS_ACCESS_KEY_ID','AWS_SECRET_ACCESS_KEY','AWS_SESSION_TOKEN']) delete env[key];
const secrets=()=>Object.entries(env).filter(([key,value])=>value&&/(PASSWORD|SECRET|ACCESS_KEY|API_KEY|TOKEN)$/.test(key)).map(([,value])=>value);
function redact(text) {for(const value of secrets()) text=text.split(value).join('[REDACTED]');return text.replace(/password=([^\s)<>]+)/gi,'password=[REDACTED]');}
const python=option('--python',existsSync(resolve(root,'services/worker/.venv/Scripts/python.exe'))?resolve(root,'services/worker/.venv/Scripts/python.exe'):'python');
const npm=process.platform==='win32'?'npm.cmd':'npm';
const gradle=process.platform==='win32'?resolve(root,'services/case-api/gradlew.bat'):'bash';
const gradlePrefix=process.platform==='win32'?[]:['services/case-api/gradlew'];
const capture=(program,values)=>execFileSync(program,values,{cwd:root,encoding:'utf8',maxBuffer:32*1024*1024}).trim();
function run(label,program,values,{cwd=root,allowFailure=false}={}) {
  console.log(`RUN ${label}`);
  const result=spawnSync(program,values,{cwd,env,encoding:'utf8',maxBuffer:64*1024*1024,shell:process.platform==='win32'&&program.endsWith('.cmd')||process.platform==='win32'&&program.endsWith('.bat')});
  const text=redact((result.stdout??'')+(result.stderr??'')+(result.error?result.error.name+'\n':''));
  writeFileSync(resolve(output,`${label}.txt`),text);
  console.log(`${label}: exit ${result.status??'launch-failure'}`);
  if(result.status!==0&&!allowFailure) throw new Error(`${label} failed; inspect redacted output/ci report`);
  return result.status===0;
}
const save=(name,value)=>writeFileSync(resolve(output,name),JSON.stringify(value,null,2)+'\n');
const sourceFiles=()=>capture('git',['ls-files','-z','--cached','--others','--exclude-standard']).split('\0').filter(Boolean)
  .filter(path=>!path.split('/').some(part=>['output','node_modules','.venv','build','.gradle','dist','generated','results','__pycache__','.pytest_cache'].includes(part))&&existsSync(resolve(root,path)));
function snapshot() {
  const target=resolve(output,'source-snapshot');mkdirSync(target,{recursive:true});
  const files=sourceFiles();
  for(const path of files) {const dest=resolve(target,path);if(!dest.startsWith(target+sep))throw new Error('Unsafe snapshot path');mkdirSync(dirname(dest),{recursive:true});copyFileSync(resolve(root,path),dest);}
  // Trivy's requirements.txt analyzer needs its documented filename; content is unchanged.
  for(const [source,dest] of [['requirements.lock','requirements.txt'],['requirements-ci.lock','requirements-ci.txt']])
    copyFileSync(resolve(root,'services/worker',source),resolve(target,'services/worker',dest));
  save('snapshot-manifest.json',{files:files.length,excluded:'Ignored files plus build/cache/generated/output/result directories; no local credentials',pythonRequirementsAlias:true});
  return target;
}
function sanitizeArtifacts() {
  function walk(directory) {for(const entry of readdirSync(directory,{withFileTypes:true})) {
    if(['source-snapshot','scanner-cache'].includes(entry.name))continue;
    const path=resolve(directory,entry.name);
    if(entry.isDirectory())walk(path);
    else if(/\.(xml|json|txt|html)$/.test(entry.name)) {const value=readFileSync(path,'utf8');const safe=redact(value);if(safe!==value)writeFileSync(path,safe);}
  }}
  walk(output);
}

try {
  if(command==='bootstrap') {
    if(envFile!==resolve(root,'.env.ci'))throw new Error('Bootstrap owns only ignored .env.ci');
    if(!existsSync(envFile)) {
      const keys=['DB_ADMIN_PASSWORD','DB_MIGRATOR_PASSWORD','DB_API_PASSWORD','DB_WORKER_PASSWORD','S3_ACCESS_KEY','S3_SECRET_KEY','KEYCLOAK_ADMIN_PASSWORD'];
      writeFileSync(envFile,keys.map(key=>`${key}=${randomBytes(24).toString('hex')}`).join('\n')+'\n',{mode:0o600,flag:'wx'});
      console.log('Created ignored synthetic CI environment; values withheld.');
    } else console.log('Existing CI environment preserved.');
  } else if(command==='up'||command==='stop') {
    if(envFile!==resolve(root,'.env.ci')||!existsSync(envFile))throw new Error('CI dependency lifecycle requires owned .env.ci');
    const operations=command==='up'?['up','-d','--wait','--wait-timeout','150','postgres','kafka','object-store']:['stop'];
    run(`dependencies-${command}`,'docker',['compose','--project-name','caseflow-ci','--env-file',envFile,'-f','compose.yaml',...operations]);
  } else if(command==='install') {
    run('npm-install',npm,['ci','--ignore-scripts'],{cwd:resolve(root,'apps/web')});
    run('python-install',python,['-m','pip','install','-r','services/worker/requirements.lock','-r','services/worker/requirements-ci.lock']);
  } else if(command==='check') {
    run('web-format',npm,['run','format:check'],{cwd:resolve(root,'apps/web')});
    const generated=['contracts/openapi/caseflow.yaml','apps/web/src/api/schema.d.ts'];
    const before=generated.map(path=>readFileSync(resolve(root,path),'utf8').replaceAll('\r\n','\n'));
    try {
      run('contract-generate',process.execPath,['scripts/generate-contract.mjs']);
      run('client-generate',npm,['run','generate:api'],{cwd:resolve(root,'apps/web')});
      if(generated.some((path,index)=>readFileSync(resolve(root,path),'utf8').replaceAll('\r\n','\n')!==before[index]))throw new Error('Generated contract/client differs; regenerate and review both files');
    } finally {generated.forEach((path,index)=>writeFileSync(resolve(root,path),before[index]));}
    run('web-build',npm,['run','build'],{cwd:resolve(root,'apps/web')});
    run('python-lint',python,['-m','ruff','check','--select','E9,F63,F7,F82','services/worker/caseflow_worker','services/worker/tests','tests/ci','scripts/ci-coverage.py']);
    run('ci-guards',python,['-m','pytest','tests/ci','-q','--tb=short',`--junitxml=${resolve(output,'ci-guards.xml')}`]);
    run('node-guards',process.execPath,['--test','tests/load/harness.test.mjs','tests/e2e/workflow-comparison.test.mjs','tests/resilience/release-guards.test.mjs','tests/resilience/release-config.test.mjs']);
    for(const file of sourceFiles().filter(path=>path.endsWith('.mjs')&&!path.startsWith('docs/'))) {
      const result=spawnSync(process.execPath,['--check',file],{cwd:root,encoding:'utf8'});
      if(result.status!==0)throw new Error(`JavaScript syntax failure: ${file}`);
    }
    save('static-summary.json',{webFormat:true,generatedContractStable:true,typescriptAndBuild:true,pythonFatalLint:true,nodeSyntax:true});
  } else if(command==='test') {
    const broad=args.includes('--broad');
    for(const name of ['DB_ADMIN_PASSWORD','DB_MIGRATOR_PASSWORD','DB_API_PASSWORD','DB_WORKER_PASSWORD'])if(!env[name])throw new Error(`Missing ${name}; bootstrap CI or select local --env-file .env`);
    env.CASEFLOW_KAFKA_PROCESS_TESTS=broad?'1':'0';
    env.COVERAGE_FILE=resolve(output,'.coverage');
    const java=run('java-tests',gradle,[...gradlePrefix,'-p','services/case-api','test','jacocoTestReport','--rerun-tasks','--console','plain',...(broad?[]:['-PciFast'])],{allowFailure:true});
    const exclusions=broad?[]:['test_process_recovery.py','test_kafka_process_recovery.py','test_deadletter_process_recovery.py','test_document_cleanup.py','test_storage_timeout_recovery.py'].flatMap(file=>['--ignore',`services/worker/tests/${file}`]);
    const worker=run('worker-tests',python,['-m','coverage','run','--branch','--source=services/worker/caseflow_worker','-m','pytest','services/worker/tests','-q','--tb=short',...exclusions,`--junitxml=${resolve(output,'worker-tests.xml')}`],{allowFailure:true});
    run('worker-coverage',python,['-m','coverage','json','-o',resolve(output,'worker-coverage.json')]);
    mkdirSync(resolve(output,'java-tests'),{recursive:true});
    for(const name of readdirSync(resolve(root,'services/case-api/build/test-results/test')).filter(name=>name.endsWith('.xml')))copyFileSync(resolve(root,'services/case-api/build/test-results/test',name),resolve(output,'java-tests',name));
    copyFileSync(resolve(root,'services/case-api/build/reports/jacoco/test/jacocoTestReport.xml'),resolve(output,'java-coverage.xml'));
    const coverage=run('critical-coverage',python,['scripts/ci-coverage.py','--java',resolve(output,'java-coverage.xml'),'--python',resolve(output,'worker-coverage.json'),'--output',resolve(output,'critical-coverage.json')],{allowFailure:true});
    save('test-summary.json',{broad,java,worker,criticalCoverage:coverage,serialDatabaseSuites:true,liveAI:false});
    if(!java||!worker||!coverage)throw new Error('Test or declared critical-branch target failed; reports preserve actual results');
  } else if(command==='images') {
    const images={};
    for(const [service,tag] of [['case-api','api'],['worker','worker']]) {
      const image=`caseflow/ci-${tag}:${randomBytes(6).toString('hex')}`;
      run(`image-build-${tag}`,'docker',['build','--file',`services/${service}/Dockerfile`,'--tag',image,'.']);
      images[tag]=capture('docker',['image','inspect',image,'--format','{{.Id}}']);
    }
    save('images.json',images);
  } else if(command==='scan') {
    const pins=JSON.parse(readFileSync(resolve(root,'tests/ci/tool-pins.json'),'utf8'));
    const source=snapshot(), cache=resolve(output,'scanner-cache');mkdirSync(cache,{recursive:true});
    const mount=['--mount',`type=bind,source=${output},target=/reports`];
    const scanEnv=['--read-only','--security-opt','no-new-privileges:true','--cap-drop','ALL','--tmpfs','/tmp:rw,nosuid,noexec,size=256m'];
    const leakConfig=['--config','/reports/source-snapshot/.gitleaks.toml'];
    const secret=run('secret-worktree','docker',['run','--rm','--network','none',...scanEnv,...mount,pins.gitleaks.image,'dir','/reports/source-snapshot',...leakConfig,'--redact=100','--no-banner','--report-format','json','--report-path','/reports/gitleaks-worktree.json'],{allowFailure:true});
    // A read-only Git object database preserves history coverage without mounting credentials.
    const history=run('secret-history','docker',['run','--rm','--network','none',...scanEnv,...mount,'--mount',`type=bind,source=${root}/.git,target=/history/.git,readonly`,pins.gitleaks.image,'git','/history',...leakConfig,'--redact=100','--no-banner','--report-format','json','--report-path','/reports/gitleaks-history.json'],{allowFailure:true});
    // The Java vulnerability database exceeds the bounded /tmp tmpfs. Keep its
    // temporary download in the owned report directory, never the host Docker socket.
    mkdirSync(resolve(output,'scanner-tmp'),{recursive:true});
    const trivy=['run','--rm',...scanEnv,...mount,'--env','TMPDIR=/reports/scanner-tmp',pins.trivy.image];
    const common=['--cache-dir','/reports/scanner-cache','--scanners','vuln','--severity','HIGH,CRITICAL','--exit-code','1','--format','json','--timeout','10m'];
    const dependencies=run('dependency-scan','docker',[...trivy,'fs',...common,'--output','/reports/dependencies.json','/reports/source-snapshot'],{allowFailure:true});
    const imagesFile=resolve(root,option('--images',relative(root,resolve(output,'images.json'))));
    const manifest=JSON.parse(readFileSync(imagesFile,'utf8')); const statuses={};
    for(const service of ['api','worker']) {
      const image=manifest[service];if(!/^sha256:[a-f0-9]{64}$/.test(image??''))throw new Error('Image scan requires immutable local image IDs');
      run(`image-save-${service}`,'docker',['save','--output',resolve(output,`${service}.tar`),image]);
      const report=resolve(output,`container-${service}.json`);
      if(existsSync(report))unlinkSync(report); // Never adjudicate an old report after scanner failure.
      const raw=run(`container-scan-${service}`,'docker',[...trivy,'image',...common,'--output',`/reports/container-${service}.json`,'--input',`/reports/${service}.tar`],{allowFailure:true});
      statuses[service]=false;
      if(existsSync(report)) {
        const found=JSON.parse(readFileSync(report,'utf8'));
        const count=(found.Results??[]).reduce((sum,item)=>sum+(item.Vulnerabilities??[]).length,0);
        if(raw||count>0) statuses[service]=run(`container-review-${service}`,python,['scripts/scan-review.py','--report',report,'--image',service,'--output',resolve(output,`container-review-${service}.json`)],{allowFailure:true});
      }
    }
    save('scan-summary.json',{secretWorktree:secret,secretHistory:history,dependencies,containers:statuses,policy:'HIGH/CRITICAL block unless an exact, unfixed worker OS HIGH finding has an unexpired documented review. Raw findings retained; not zero vulnerabilities.',dockerSocketMounted:false});
    if(!secret||!history||!dependencies||Object.values(statuses).some(value=>!value))throw new Error('Scan gate failed; inspect redacted findings and remediate or record a specific reviewed exception');
  } else if(command==='terraform') {
    run('terraform-format','terraform',['-chdir=infrastructure/terraform/rehearsal','fmt','-check','-recursive']);
    run('terraform-init','terraform',['-chdir=infrastructure/terraform/rehearsal','init','-backend=false','-input=false']);
    run('terraform-validate','terraform',['-chdir=infrastructure/terraform/rehearsal','validate','-no-color']);
    run('terraform-mock-tests','terraform',['-chdir=infrastructure/terraform/rehearsal','test','-no-color']);
    run('terraform-bootstrap-test',python,['-m','pytest','infrastructure/terraform/rehearsal/test_bootstrap.py','-q','--tb=short']);
  } else if(command==='redact') {
    sanitizeArtifacts();console.log('CI text artifacts sanitized against loaded environment values.');
  } else throw new Error('Usage: node scripts/ci.mjs bootstrap|up|install|check|test [--broad]|images|scan|terraform|stop|redact [--env-file .env] [--output output/ci]');
} finally {sanitizeArtifacts();}
