import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {pathToFileURL} from 'node:url';

export const revision = '742e9f0afd1e303117fa28c41c9ef50b9b7e3d66';
const source = 'git:github.com/Aaalice233/pi-image-budget@' + revision;
const digest = '6bdca5e7e09c9664540417e1808b8beddbc503402a75a87cf2d482b280a2a78e';
const modules = ['budget.ts', 'config.ts', 'errors.ts', 'image.ts', 'json-size.ts', 'payload.ts', 'resize.ts'];

const depot = base => path.join(base, '.agents-sot-image-budget');
const generation = base => path.join(depot(base), revision);

function stat(file) {
  return fs.lstatSync(file,{throwIfNoEntry:false});
}

function directory(file) {
  if (!stat(file)?.isDirectory()) throw Error('managed image-budget directory missing or linked; run make install PROVIDER=pi');
}

function within(root, file) {
  const relative = path.relative(root, file);
  return relative && relative !== '..' && !relative.startsWith('..'+path.sep) && !path.isAbsolute(relative);
}

function verifyEngine(dir) {
  directory(dir);
  directory(path.join(dir,'src'));
  const check = createHash('sha256');
  for (const name of modules) {
    const file = path.join(dir,'src',name);
    if (!stat(file)?.isFile()) throw Error('managed image-budget module missing or linked');
    check.update(name+'\0').update(fs.readFileSync(file));
  }
  if (check.digest('hex') !== digest) throw Error('managed image-budget checkout differs from the pinned source');
  return dir;
}

function readReceipt(dir, root) {
  directory(dir);
  const file = path.join(dir,'ownership.json');
  if (!stat(file)?.isFile()) throw Error('managed image-budget ownership record missing or linked');
  const receipt = JSON.parse(fs.readFileSync(file,'utf8'));
  if (receipt.root !== path.resolve(root) || receipt.revision !== path.basename(dir) || typeof receipt.package !== 'string') {
    throw Error('managed image-budget checkout belongs to another source or has invalid ownership');
  }
  const local = path.resolve(dir,receipt.package);
  if (!within(dir,local) || fs.realpathSync(local) !== local) {
    throw Error('managed image-budget checkout escapes its cache');
  }
  return local;
}

export function imageEngine(base, root) {
  directory(depot(base));
  return verifyEngine(readReceipt(generation(base),root));
}

async function installPinned(manager) {
  if (process.platform !== 'win32') return manager.install(source);
  const offset = Number(process.env.GIT_CONFIG_COUNT || 0);
  if (!Number.isSafeInteger(offset) || offset < 0) throw Error('invalid inherited Git configuration count');
  // Apply only to the Git subprocesses of this install, including Git's nested index-pack.
  const settings = {
    GIT_CONFIG_COUNT:String(offset+2),
    [`GIT_CONFIG_KEY_${offset}`]:'core.longpaths',
    [`GIT_CONFIG_VALUE_${offset}`]:'true',
    [`GIT_CONFIG_KEY_${offset+1}`]:'core.autocrlf',
    [`GIT_CONFIG_VALUE_${offset+1}`]:'false',
  };
  const inherited = Object.fromEntries(Object.keys(settings).map(key=>[key,process.env[key]]));
  try {
    Object.assign(process.env,settings);
    await manager.install(source);
  } finally {
    for (const [key,value] of Object.entries(inherited)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  }
}

export async function acquireImageEngine(base, root, cli) {
  const parent = depot(base), target = generation(base);
  const receipt = path.join(target,'ownership.json');
  if (stat(parent)) directory(parent);
  if (stat(target)) directory(target);
  if (stat(receipt)) return imageEngine(base,root);
  fs.mkdirSync(target,{recursive:true,mode:0o700});
  if (fs.readdirSync(target).some(name => name !== 'ownership.json' && !/^\.install-[A-Za-z0-9]{6}$/.test(name))) {
    throw Error('managed image-budget generation contains files without ownership');
  }
  const staging = fs.mkdtempSync(path.join(target,'.install-'));
  let installed = false;
  try {
    const packageDir = path.resolve(path.dirname(cli),'../..');
    const {DefaultPackageManager,SettingsManager} = await import(pathToFileURL(path.join(packageDir,'dist/index.js')));
    const manager = new DefaultPackageManager({cwd:staging,agentDir:staging,settingsManager:SettingsManager.inMemory()});
    await installPinned(manager);
    const checkout = manager.getInstalledPath(source,'user');
    if (!checkout || !within(staging,checkout)) throw Error('Pi installed image-budget outside the managed cache');
    verifyEngine(checkout);
    const candidate = path.join(staging,'ownership.json');
    fs.writeFileSync(candidate,JSON.stringify({
      root:path.resolve(root),revision,package:path.relative(target,checkout),
    })+'\n',{flag:'wx',mode:0o600});
    // Publish only the verified receipt. Windows can deny renaming a populated Git checkout.
    try {
      fs.linkSync(candidate,receipt);
      installed = true;
    } catch (error) {
      if (error.code !== 'EEXIST') throw error;
    }
    return imageEngine(base,root);
  } finally {
    if (!installed) fs.rmSync(staging,{recursive:true,force:true,maxRetries:4});
  }
}

export function removeImageEngines(base, root, dryRun = false) {
  const parent=depot(base);
  if (!stat(parent)) return;
  directory(parent);
  const candidates=[];
  for (const name of fs.readdirSync(parent)) {
    if (!/^[0-9a-f]{40}$/.test(name)) continue;
    const dir=path.join(parent,name),receipt=path.join(dir,'ownership.json');
    if (!stat(dir)?.isDirectory() || !stat(receipt)?.isFile()) continue;
    const data=JSON.parse(fs.readFileSync(receipt,'utf8'));
    if (data.root !== path.resolve(root)) continue;
    const checkout=readReceipt(dir,root);
    if (name===revision) verifyEngine(checkout);
    candidates.push(dir);
  }
  if (dryRun) return;
  for (const dir of candidates) fs.rmSync(dir,{recursive:true});
  if (!fs.readdirSync(parent).length) fs.rmdirSync(parent);
}
