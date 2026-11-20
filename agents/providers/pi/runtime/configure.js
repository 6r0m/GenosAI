import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {createRequire} from 'node:module';
import {fileURLToPath, pathToFileURL} from 'node:url';

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
export async function configure({op, dir, root, secretRoot = path.join(root, "secrets"), profiles, profileFile, requireKey = true, cli, expected, profileId, setup = false}) {
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
  const chosen = op === 'uninstall' ? null : resolveProfiles(profiles !== undefined ? profiles : readProfiles(profileFile ?? defaultProfileFile), setup);
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
  if(op !== 'validate') {
    fs.mkdirSync(dir, {recursive: true});
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
    const auth = read(authPath), models = read(modelsPath), state = read(statePath);
    if(models.providers !== undefined && !object(models.providers))throw Error('native model providers must be an object');
    if(state.managed !== undefined && !object(state.managed))throw Error('managed ownership must be an object');
    for(const value of Object.values(state.managed ?? {}))if(!object(value))throw Error('managed entries must be objects');
    if(state.root && path.resolve(state.root) !== root)throw Error('configuration belongs to another SOT');
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
    if(op === 'validate')return {profile: chosen.active, provider: chosen.profiles[chosen.active].provider, model: chosen.profiles[chosen.active].model, thinking: chosen.profiles[chosen.active].thinking};
    // All ownership/collision checks precede the first write; each promoted file is validated JSON.
    if(!equal(auth, read(authPath)))atomic(authPath, auth);
    if(Object.keys(modelProviders).length || models.providers) {
      models.providers = modelProviders;
      if(!equal(models, read(modelsPath)))atomic(modelsPath, models);
    }
    if(op === 'uninstall') {
      if(fs.existsSync(statePath))fs.unlinkSync(statePath);
      return {profile: null, provider: null, model: null, thinking: null};
    }
    atomic(statePath, {root, profile: chosen.active, managed});
    return {profile: chosen.active, provider: chosen.profiles[chosen.active].provider, model: chosen.profiles[chosen.active].model, thinking: chosen.profiles[chosen.active].thinking};
  } finally {if(op !== 'validate')fs.rmdirSync(lock);}
}
if(process.argv[1] === new URL(import.meta.url).pathname || process.argv[1]?.replaceAll('\\', '/').endsWith('/configure.js')) {
  const args=process.argv.slice(2); const localMode=args.at(-1)==='--local'; if(localMode)args.pop();
  const setup=args.at(-1)==='--setup'; if(setup)args.pop();
  const [op, dir, root, cli, expected, profileId] = args;
  try {
    const input=localMode ? JSON.parse(fs.readFileSync(0,'utf8')) : {};
    if(localMode && (typeof input.root!=='string' || typeof input.secretRoot!=='string' || typeof input.configured!=='boolean'))throw Error('local configuration reader unavailable');
    if(op==='schema') {resolveProfiles(input.profiles, setup);process.exit(0);}
    const result = await configure({op: op === 'resolve' ? 'validate' : op, dir, root, cli, expected, profileId, setup,
      ...(localMode ? {root:input.root,secretRoot:input.secretRoot,profiles:input.profiles} : {}), requireKey: op !== 'uninstall'});
    // Selection is returned from the same snapshot that was validated, and projected for install.
    if(op === 'resolve' || op === 'install')process.stdout.write([result.profile, result.provider, result.model, result.thinking].join('\t') + '\n');
  }
  catch(err) {console.error('pi-config: ' + err.message);process.exitCode = 1;}
}
