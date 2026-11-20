import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {createRequire} from 'node:module';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {spawnSync} from 'node:child_process';

// Pi owns provider compatibility and thinking-level semantics. This file owns only the
// connection-profile schema, the pinned-catalog projection and native ownership checks.
const here = path.dirname(fileURLToPath(import.meta.url));
const defaultProfileFile = path.join(here, 'profiles.json');
const THINKING_LEVELS = ['off', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max'];
const PROFILE_KEYS = new Set(['provider', 'model', 'credential', 'thinking', 'endpoint', 'api', 'compatibleModel']);
const MODEL_KEYS = new Set(['name', 'reasoning', 'input', 'contextWindow', 'maxTokens', 'thinkingLevelMap', 'compat']);
const ID = /^[a-z][a-z0-9-]*$/;

function read(file) {
  if(!fs.existsSync(file))return {};
  const data = JSON.parse(fs.readFileSync(file, 'utf8'));
  if(!data || typeof data !== 'object' || Array.isArray(data))throw Error('configuration must be an object');
  return data;
}
function readProfiles(file) {
  if(!fs.existsSync(file))throw Error('profile configuration missing: ' + file);
  let data;
  try {data = JSON.parse(fs.readFileSync(file, 'utf8'));}
  catch {throw Error('profile configuration is not valid JSON: ' + file);}
  if(!data || typeof data !== 'object' || Array.isArray(data))throw Error('profile configuration must be an object: ' + file);
  return data;
}
const equal = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const object = value => Boolean(value) && typeof value === 'object' && !Array.isArray(value);
const quote = s => "'" + s.replaceAll("'", "'\\''") + "'";

// One named schema for connection profiles; every accepted key is deliberate and unknown keys fail closed.
function resolveProfiles(data, setup = false) {
  const unknown = Object.keys(data).filter(key => key !== 'active' && key !== 'profiles');
  if(unknown.length)throw Error('unknown profile configuration keys: ' + unknown.join(', '));
  if(data.active===null && object(data.profiles) && Object.keys(data.profiles).length===0) {
    if(setup)return null;
    throw Error('Pi is unconfigured; add a private connection profile to config.local.jsonc before starting a session');
  }
  if(typeof data.active !== 'string' || !ID.test(data.active))throw Error('invalid active profile id');
  if(!object(data.profiles) || Object.keys(data.profiles).length === 0)throw Error('profiles must be a non-empty object');
  const profiles = {};
  for(const [id, entry] of Object.entries(data.profiles)) {
    if(!ID.test(id))throw Error('invalid profile id: ' + id);
    if(!object(entry))throw Error('profile must be an object: ' + id);
    const extra = Object.keys(entry).filter(key => !PROFILE_KEYS.has(key));
    if(extra.length)throw Error('unknown keys for profile ' + id + ': ' + extra.join(', '));
    if(typeof entry.provider !== 'string' || !ID.test(entry.provider))throw Error('invalid provider for profile ' + id);
    if(typeof entry.model !== 'string' || !entry.model)throw Error('invalid model for profile ' + id);
    if(typeof entry.credential !== 'string' || !entry.credential.startsWith('secrets/') || !entry.credential.endsWith('.key') || entry.credential.includes('..'))
      throw Error('invalid credential reference for profile ' + id);
    const endpoint = entry.endpoint ?? '';
    if(typeof endpoint !== 'string' || (endpoint && !endpoint.startsWith('https://') && !endpoint.startsWith('http://127.0.0.1:')))
      throw Error('invalid endpoint for profile ' + id);
    const api = entry.api ?? '';
    if(api && api !== 'openai-completions' && api !== 'anthropic-messages')throw Error('invalid API for profile ' + id);
    const thinking = entry.thinking ?? '';
    if(thinking && !THINKING_LEVELS.includes(thinking))throw Error('invalid thinking level for profile ' + id + ': ' + thinking);
    const custom = Object.hasOwn(entry, 'compatibleModel');
    if(custom) {
      if(!object(entry.compatibleModel))throw Error('compatible model must be an object for profile ' + id);
      const extra = Object.keys(entry.compatibleModel).filter(key => !MODEL_KEYS.has(key));
      if(extra.length)throw Error('unknown compatible model keys for profile ' + id + ': ' + extra.join(', '));
      if(!endpoint || !api)throw Error('compatible model requires explicit endpoint and API for profile ' + id);
      if(entry.compatibleModel.thinkingLevelMap !== undefined && (!object(entry.compatibleModel.thinkingLevelMap) || Object.keys(entry.compatibleModel.thinkingLevelMap).some(key => !THINKING_LEVELS.includes(key))))
        throw Error('invalid compatible thinking map for profile ' + id);
      if(entry.compatibleModel.compat !== undefined && !object(entry.compatibleModel.compat))throw Error('compatible model compat must be an object for profile ' + id);
    }
    profiles[id] = {provider: entry.provider, model: entry.model, credential: entry.credential, thinking, endpoint, api, ...(custom ? {compatibleModel: entry.compatibleModel} : {})};
  }
  if(!Object.hasOwn(profiles,data.active))throw Error('active profile is not defined: ' + data.active);
  return {active: data.active, profiles};
}

// @earendil-works/pi-ai ships the provider catalog and the thinking-level capability. A
// shrinkwrapped runtime nests that dependency under the coding-agent package while a flat install
// hoists it to the prefix, so search the module ancestors the way Node resolves a bare import.
function nativeDependency(cli, name) {
  for(let dir = path.dirname(path.resolve(cli));;) {
    const candidate = path.join(dir, 'node_modules', name);
    try {if(fs.statSync(candidate).isDirectory())return candidate;} catch {}
    const parent = path.dirname(dir);
    if(parent === dir)return null;
    dir = parent;
  }
}
// The pinned native runtime supplies both the model catalog and the capability function;
// nothing here reimplements provider compatibility or clamps silently.
async function verifyCatalog(chosen, cli, expected) {
  if(expected) {
    const version = read(path.resolve(path.dirname(cli), '../../package.json')).version;
    if(version !== expected)throw Error('installed Pi ' + (version ?? 'unknown') + ' does not match managed pin ' + expected + '; run install.sh --provider pi --runtime');
  }
  if(!chosen)return;
  const profile = chosen.profiles[chosen.active];
  const aiDir = nativeDependency(cli, '@earendil-works/pi-ai');
  if(!aiDir)throw Error('native Pi dependency missing (is the pinned runtime installed?): @earendil-works/pi-ai');
  const catalogPath = path.join(aiDir, 'dist/providers/data', profile.provider + '.json');
  let found;
  if(profile.compatibleModel) {
    if(fs.existsSync(catalogPath))throw Error('compatible model cannot replace a native provider catalog: ' + profile.provider);
    found = {id: profile.model, ...profile.compatibleModel, api: profile.api, baseUrl: profile.endpoint};
    const codingDir = path.resolve(path.dirname(cli), '../..');
    const require = createRequire(fs.realpathSync(path.join(codingDir, 'package.json')));
    const {ModelsJsonSchemas} = await import(pathToFileURL(path.join(codingDir, 'dist/core/model-config.js')).href);
    const {Compile} = await import(pathToFileURL(require.resolve('typebox/compile')).href);
    const schema = ModelsJsonSchemas?.model;
    if(!object(schema?.properties?.compat?.properties) || !object(schema?.properties?.thinkingLevelMap?.properties) || typeof Compile !== 'function')throw Error('native compatible model schema unavailable');
    // Native schemas own field types. The managed surface additionally rejects unknown keys.
    const checked = Compile({...schema, additionalProperties: false, properties: {...schema.properties,
      compat: {...schema.properties.compat, additionalProperties: false},
      thinkingLevelMap: {...schema.properties.thinkingLevelMap, additionalProperties: false}}});
    if(!checked.Check(found))throw Error('invalid compatible model definition for profile ' + chosen.active);
  } else {
    if(!fs.existsSync(catalogPath))throw Error('unsupported native provider catalog: ' + profile.provider);
    const catalog = read(catalogPath);
    found = Object.values(catalog).flatMap(group => Object.values(group)).find(entry => entry.id === profile.model);
    if(!found)throw Error('model unavailable in pinned native catalog: ' + profile.provider + '/' + profile.model);
    if(profile.api && profile.api !== found.api)throw Error('profile API does not match native model catalog');
  }
  if(profile.thinking) {
    const capabilityPath = path.join(aiDir, 'dist/index.js');
    if(!fs.existsSync(capabilityPath))throw Error('native capability module missing: ' + capabilityPath);
    const capability = await import(pathToFileURL(capabilityPath).href);
    if(typeof capability.getSupportedThinkingLevels !== 'function')throw Error('native capability export missing');
    const levels = capability.getSupportedThinkingLevels(found);
    if(!Array.isArray(levels) || !levels.includes(profile.thinking))
      throw Error('thinking level ' + profile.thinking + ' unsupported by pinned ' + profile.provider + '/' + profile.model + ' (supported: ' + levels.join(', ') + ')');
  }
  return found;
}

function atomic(file, data) {
  const temp = file + '.' + crypto.randomUUID() + '.tmp';
  try {fs.writeFileSync(temp, JSON.stringify(data, null, 2) + '\n', {mode: 0o600, flag: 'wx'});fs.renameSync(temp, file);}
  finally {if(fs.existsSync(temp))fs.unlinkSync(temp);}
}
function stat(file) {
  try {return fs.lstatSync(file);} catch(error) {if(error.code === 'ENOENT')return null;throw error;}
}
function ordinaryDirectory(file) {
  const info=stat(file);
  if(info && (!info.isDirectory() || info.isSymbolicLink()))throw Error('foreign or symbolic profile directory: ' + file);
}
const ownsPackage=(entry,dir,resources)=>typeof entry==='string' && path.resolve(dir,entry)===resources.packageRoot;
function resourceCheck(dir, resources, state) {
  ordinaryDirectory(resources.sessions);
  if(!fs.statSync(resources.instructions).isFile() || !fs.statSync(path.join(resources.packageRoot,'package.json')).isFile())throw Error('canonical Pi package resources unavailable');
  if(state.resources && !equal(state.resources,resources))throw Error('managed profile resource ownership changed');
  if(!state.resources && stat(dir) && fs.readdirSync(dir).some(name=>name!=='.agents-sot.lock'))throw Error('foreign profile directory left alone');
  for(const [name,target] of [['AGENTS.md',resources.instructions],['sessions',resources.sessions]]) {
    const file=path.join(dir,name),info=stat(file);
    if(info && (!info.isSymbolicLink() || fs.realpathSync(file)!==fs.realpathSync(target)))
      throw Error('foreign or tampered profile link: ' + name);
  }
  const settings=read(path.join(dir,'settings.json'));
  if(settings.packages!==undefined && !Array.isArray(settings.packages))throw Error('native packages must be an array');
  if((settings.packages??[]).some(entry=>object(entry) && ownsPackage(entry.source,dir,resources)))throw Error('managed package reference changed');
  if(!state.resources && stat(path.join(dir,'settings.json')))throw Error('foreign profile settings left alone');
  return settings;
}
function nativePackage(cli, dir, resources, action) {
  if(!cli || !fs.existsSync(cli))throw Error('native Pi required for profile package ' + action);
  const result=spawnSync(process.execPath,[cli,action,resources.packageRoot,'--no-approve'],{
    cwd:resources.packageRoot,env:{...process.env,PI_CODING_AGENT_DIR:dir,PI_TELEMETRY:'0',PI_OFFLINE:'1'},encoding:'utf8',timeout:30000});
  if(result.error || result.status!==0)throw Error('native profile package '+action+' failed: '+(result.error?.message??result.stderr.trim()));
}
function provision(dir, resources, cli) {
  fs.mkdirSync(resources.sessions,{recursive:true,mode:0o700});
  for(const [name,target,type] of [['AGENTS.md',resources.instructions,'file'],['sessions',resources.sessions,process.platform==='win32'?'junction':'dir']])
    if(!stat(path.join(dir,name)))fs.symlinkSync(target,path.join(dir,name),type);
  const settings=read(path.join(dir,'settings.json'));
  if(!(settings.packages??[]).some(entry=>ownsPackage(entry,dir,resources)))nativePackage(cli,dir,resources,'install');
  if(!(read(path.join(dir,'settings.json')).packages??[]).some(entry=>ownsPackage(entry,dir,resources)))throw Error('native profile package registration missing');
}
function removeResources(dir, resources, cli) {
  const settings=read(path.join(dir,'settings.json'));
  if((settings.packages??[]).some(entry=>ownsPackage(entry,dir,resources))) {
    if(cli && fs.existsSync(cli))nativePackage(cli,dir,resources,'remove');
    else {settings.packages=settings.packages.filter(entry=>!ownsPackage(entry,dir,resources));atomic(path.join(dir,'settings.json'),settings);}
  }
  // Ownership was checked against each exact target; unlink never traverses a directory junction.
  for(const name of ['AGENTS.md','sessions'])if(stat(path.join(dir,name)))fs.unlinkSync(path.join(dir,name));
}
export async function configure(options) {
  if(options.profileScope)return configureProfile(options);
  return project(options);
}
async function project({op, dir, root, secretRoot = path.join(root, "secrets"), profiles, profileFile, requireKey = true, cli, expected, profileId, setup = false, resources, dryRun=false}) {
  root = path.resolve(root);dir = path.resolve(dir);
  secretRoot=path.resolve(secretRoot);
  const credentialPath = reference => {
    const resolved=path.resolve(secretRoot,reference.slice('secrets/'.length));
    const relative=path.relative(secretRoot,resolved);
    if(relative.startsWith('..') || path.isAbsolute(relative))throw Error('invalid credential reference');
    if(fs.existsSync(resolved)) {
      const realRelative=path.relative(fs.realpathSync(secretRoot),fs.realpathSync(resolved));
      if(realRelative.startsWith('..') || path.isAbsolute(realRelative))throw Error('credential reference escapes its configured owner');
    }
    return resolved;
  };
  if(!['install', 'uninstall', 'validate'].includes(op))throw Error('unsupported configuration operation');
  const chosen = op === 'uninstall' ? null : resolveProfiles(profiles ?? readProfiles(profileFile ?? defaultProfileFile), setup);
  if(chosen && profileId !== undefined) {
    if(typeof profileId !== 'string' || !ID.test(profileId))throw Error('invalid profile selector');
    if(!Object.hasOwn(chosen.profiles,profileId))throw Error('unknown profile selector; available profiles: ' + Object.keys(chosen.profiles).join(', '));
    chosen.active = profileId;
  }
  let catalogModel;
  if(chosen) {
    const profile = chosen.profiles[chosen.active];
    const credential = profile.credential;
    if(profile.compatibleModel)catalogModel = {id: profile.model, ...profile.compatibleModel, api: profile.api, baseUrl: profile.endpoint};
    const resolved = credentialPath(credential);
    // Commands defer plaintext credential access to Pi's native authentication owner.
    if(requireKey && !setup) {
      if(!fs.existsSync(resolved))throw Error('credential file missing: configure the private credential directory and provide the selected profile key');
      if(!fs.statSync(resolved).isFile())throw Error('credential reference must be a regular file');
      fs.accessSync(resolved, fs.constants.R_OK);
    }
  }
  if(cli && op !== 'uninstall')catalogModel = await verifyCatalog(chosen, cli, expected);
  const lock = path.join(dir, '.agents-sot.lock');
  if(op !== 'validate' && !dryRun) {
    fs.mkdirSync(dir, {recursive: true,mode:0o700});
    const until = Date.now() + 5000;
    while(true) {
      try {fs.mkdirSync(lock);break;}
      catch(err) {
        if(err.code !== 'EEXIST' || Date.now() > until)throw Error('configuration lock unavailable; inspect ' + lock);
        Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 25);
      }
    }
  }
  try {
    const authPath = path.join(dir, 'auth.json'), modelsPath = path.join(dir, 'models.json'), statePath = path.join(dir, 'agents-sot-state.json');
    if(resources)for(const file of [authPath,modelsPath,statePath,path.join(dir,'settings.json')])
      if(stat(file)?.isSymbolicLink())throw Error('symbolic native profile file refused');
    const auth = read(authPath), models = read(modelsPath), state = read(statePath);
    if(models.providers !== undefined && !object(models.providers))throw Error('native model providers must be an object');
    if(state.managed !== undefined && !object(state.managed))throw Error('managed ownership must be an object');
    for(const value of Object.values(state.managed ?? {}))if(!object(value))throw Error('managed entries must be objects');
    if((state.root && path.resolve(state.root) !== root) || (resources && state.resources && !state.root))throw Error('configuration belongs to another SOT');
    if(resources)resourceCheck(dir,resources,state);
    const old = state.managed ?? {};
    if(op !== 'uninstall' && !chosen) {
      if(Object.values(old).some(entries => Object.keys(entries).length))throw Error('existing managed connection requires a configured profile; refusing to clear it during setup');
      return {profile: null, provider: null, model: null, thinking: null};
    }
    const modelProviders = models.providers ?? {};
    for(const [id, value] of Object.entries(old.auth ?? {})) {
      if(!equal(auth[id], value))throw Error('managed authentication changed; refusing drift for ' + id);
      delete auth[id];
    }
    for(const [id, value] of Object.entries(old.models ?? {})) {
      if(!equal(modelProviders[id], value))throw Error('managed model configuration changed; refusing drift for ' + id);
      delete modelProviders[id];
    }
    const managed = {auth: {}, models: {}};
    if(op !== 'uninstall') {
      const profile = chosen.profiles[chosen.active];
      const resolved = credentialPath(profile.credential);
      if(auth[profile.provider] !== undefined)throw Error('foreign authentication collision for ' + profile.provider);
      if(modelProviders[profile.provider] !== undefined)throw Error('foreign model configuration collision for ' + profile.provider);
      const command = process.platform === 'win32' ? `!powershell.exe -NoProfile -Command "[IO.File]::ReadAllText('${resolved.replaceAll("'", "''")}').Trim()"` : `!cat -- ${quote(resolved)}`;
      managed.auth[profile.provider] = {type: 'api_key', key: command};auth[profile.provider] = managed.auth[profile.provider];
      if(catalogModel || profile.endpoint || profile.api) {
        managed.models[profile.provider] = {...(profile.endpoint ? {baseUrl: profile.endpoint} : {}), ...(profile.api ? {api: profile.api} : {})};
        if(profile.compatibleModel)managed.models[profile.provider].authHeader = true;
        if(catalogModel) {
          // Pi overlays newer cached catalogs. Project the validated selected model above that layer
          // so native dispatch uses the same endpoint and reasoning metadata as preflight.
          const model = {...catalogModel, ...(profile.endpoint ? {baseUrl: profile.endpoint} : {})};
          delete model.provider;delete model.type;
          managed.models[profile.provider].models = [model];
        }
        modelProviders[profile.provider] = managed.models[profile.provider];
      }
    }
    if(op === 'validate' || dryRun)return chosen ? {profile: chosen.active, provider: chosen.profiles[chosen.active].provider, model: chosen.profiles[chosen.active].model, thinking: chosen.profiles[chosen.active].thinking} : {};
    if(resources && op!=='uninstall') {
      // Record partial provisioning ownership so a failed local package install can be retried.
      atomic(statePath,{root,profile:chosen.active,managed:old,resources});
      provision(dir,resources,cli);
    }
    // Failed native removal must leave the recorded connection projections available for retry.
    if(resources && op==='uninstall')removeResources(dir,resources,cli);
    // All ownership/collision checks precede the first write; each promoted file is validated JSON.
    if(!equal(auth, read(authPath)))atomic(authPath, auth);
    if(Object.keys(modelProviders).length || models.providers) {
      models.providers = modelProviders;
      if(!equal(models, read(modelsPath)))atomic(modelsPath, models);
    }
    if(op === 'uninstall') {
      if(resources)atomic(statePath,{root,profile:state.profile,managed:{},resources});
      else if(fs.existsSync(statePath))fs.unlinkSync(statePath);
      return {profile: null, provider: null, model: null, thinking: null};
    }
    atomic(statePath, {root, profile: chosen.active, managed,...(resources?{resources}:{})});
    return {profile: chosen.active, provider: chosen.profiles[chosen.active].provider, model: chosen.profiles[chosen.active].model, thinking: chosen.profiles[chosen.active].thinking};
  } finally {if(op !== 'validate' && !dryRun)fs.rmdirSync(lock);}
}
async function configureProfile(options) {
  const {op,profileId,setup=false}=options,base=path.resolve(options.dir),container=path.join(base,'profiles');
  ordinaryDirectory(base);ordinaryDirectory(container);
  const packageRoot=path.resolve(here,'../../..');
  const resources={packageRoot,instructions:path.join(packageRoot,'AGENTS.md'),sessions:path.join(base,'sessions')};
  const legacy={...options,profileScope:false,dir:base,op:'uninstall',resources:undefined};
  if(op==='retire')return {...await project(legacy),agentDir:base};
  if(op==='uninstall') {
    if(!stat(base))return {agentDir:base};
    const owned=[];
    if(stat(container))for(const name of fs.readdirSync(container)) {
      if(!ID.test(name))continue;
      const dir=path.join(container,name);
      if(!stat(path.join(dir,'agents-sot-state.json')))continue;
      ordinaryDirectory(dir);
      owned.push({...options,dir,resources,profileScope:false});
    }
    for(const entry of [...owned,legacy])await project({...entry,dryRun:true});
    for(const entry of [...owned,legacy])await project(entry);
    return {agentDir:base};
  }
  const chosen = op === 'uninstall' ? null : resolveProfiles(options.profiles !== undefined ? options.profiles : readProfiles(options.profileFile ?? defaultProfileFile), setup || op==='inspect');
  if(profileId!==undefined) {
    if(!chosen || typeof profileId!=='string' || !ID.test(profileId) || !Object.hasOwn(chosen.profiles,profileId))throw Error('invalid or unknown profile selector');
    chosen.active=profileId;
  }
  if(!chosen) {
    if(op==='inspect') {if(!stat(base))throw Error('native Pi directory not initialized');return {agentDir:base};}
    if(stat(container))for(const name of fs.readdirSync(container)) {
      if(!ID.test(name))continue;
      const dir=path.join(container,name),statePath=path.join(dir,'agents-sot-state.json');
      ordinaryDirectory(dir);
      if(stat(statePath)?.isSymbolicLink())throw Error('symbolic native profile file refused');
      if(Object.values(read(statePath).managed??{}).some(entries=>Object.keys(entries).length))throw Error('existing managed connection requires a configured profile');
    }
    return {...await project({...options,profiles:{active:null,profiles:{}},profileScope:false}),agentDir:base};
  }
  const dir=path.join(container,chosen.active);ordinaryDirectory(dir);
  const selected={profile:chosen.active,...chosen.profiles[chosen.active],agentDir:dir};
  if(op==='inspect') {
    const state=read(path.join(dir,'agents-sot-state.json'));
    if(!stat(dir) || !state.resources || !stat(path.join(dir,'AGENTS.md')) || !stat(path.join(dir,'sessions')) || !(read(path.join(dir,'settings.json')).packages??[]).some(entry=>ownsPackage(entry,dir,resources)))throw Error('selected profile not initialized; launch it before package inspection');
    if(path.resolve(state.root??'')!==path.resolve(options.root))throw Error('configuration belongs to another SOT');
    resourceCheck(dir,resources,state);
    if(options.cli)await verifyCatalog(null,options.cli,options.expected);
    return selected;
  }
  if(setup)await project({...legacy,dryRun:true});
  const projection={...options,dir,profiles:chosen,profileId:undefined,resources,profileScope:false};
  const validated=await project({...projection,op:'validate'});
  if(op==='validate')return {...validated,agentDir:dir};
  return {...await project(projection),agentDir:dir};
}
if(process.argv[1] === new URL(import.meta.url).pathname || process.argv[1]?.replaceAll('\\', '/').endsWith('/configure.js')) {
  const args=process.argv.slice(2); const localMode=args.at(-1)==='--local'; if(localMode)args.pop();
  const setup=args.at(-1)==='--setup'; if(setup)args.pop();
  const [op, dir, root, cli, expected, profileId] = args;
  try {
    const input=localMode ? JSON.parse(fs.readFileSync(0,'utf8')) : {};
    if(localMode && (typeof input.root!=='string' || typeof input.secretRoot!=='string' || typeof input.configured!=='boolean'))throw Error('local configuration reader unavailable');
    if(op==='schema') {resolveProfiles(input.profiles, setup);process.exit(0);}
    const result = await configure({op: op === 'resolve' ? 'validate' : op, dir, root, cli, expected, profileId, setup,profileScope:true,
      ...(localMode ? {root:input.root,secretRoot:input.secretRoot,profiles:input.profiles} : {}), requireKey: op !== 'uninstall'});
    // Selection is returned from the same snapshot that was validated, and projected for install.
    if(op === 'resolve' || op === 'install' || op==='inspect')process.stdout.write([result.profile??'-', result.provider??'-', result.model??'-', result.agentDir,result.thinking].join('\t') + '\n');
  }
  catch(err) {console.error('pi-config: ' + err.message);process.exitCode = 1;}
}
