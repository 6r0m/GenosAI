#!/usr/bin/env python3
"""Build and check source-only distributions without opening private input files."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
SOURCE_MANIFEST=Path('tools/source-manifest.json')
PRIVATE_DIRS={'.git','tmp','node_modules','__pycache__','.trash','synced','.playwright','.playwright-cli','.venv','logs','.cache','.pytest_cache','.mypy_cache','.ruff_cache','.toolchain','.claude','.codex','.pi','.agents'}
PRIVATE_SUFFIXES={'.key','.pem','.p12','.pfx','.log','.bak','.tmp','.pyc','.pyo'}
PRIVATE_NAMES={'config.local.json','config.local.jsonc','machine.json','repos.json','.env'}
LOWER_DIRS={name.casefold() for name in PRIVATE_DIRS}
LOWER_SUFFIXES={name.casefold() for name in PRIVATE_SUFFIXES}
LOWER_NAMES={name.casefold() for name in PRIVATE_NAMES}
WINDOWS_FORBIDDEN=set('<>:"\\|?*')
WINDOWS_RESERVED={'con','prn','aux','nul'}|{'com%d'%i for i in range(1,10)}|{'lpt%d'%i for i in range(1,10)}

def private(relative):
    parts=[part.casefold() for part in relative.parts]
    name=relative.name.casefold()
    return (any(p in LOWER_DIRS for p in parts) or
            (parts[0]=='secrets' and len(parts)>1 and relative.as_posix()!='secrets/README.md') or
            name in LOWER_NAMES or any(name.startswith(n+'.') for n in ('config.local.json','config.local.jsonc')) or
            (name.startswith('.env.') and name!='.env.example') or
            relative.suffix.casefold() in LOWER_SUFFIXES)

def portable(name):
    if not name: return False
    for part in name.split('/'):
        if part in ('','.','..'): return False
        if any(c in WINDOWS_FORBIDDEN or ord(c)<32 for c in part): return False
        if part.endswith((' ','.')): return False
        if part.split('.',1)[0].casefold() in WINDOWS_RESERVED: return False
    return True

def case_collisions(names):
    grouped={}
    for name in names: grouped.setdefault(name.casefold(),set()).add(name)
    return sorted((key,sorted(paths)) for key,paths in grouped.items() if len(paths)>1)

def with_parents(names):
    expanded=set(names)
    for name in names:
        expanded.update(parent.as_posix() for parent in Path(name).parents if parent!=Path('.'))
    return expanded

def admitted_files(root):
    for relative in (SOURCE_MANIFEST.parent,SOURCE_MANIFEST):
        if (root/relative).is_symlink():
            raise ValueError('source link requires explicit disposition: '+str(relative))
    data=json.loads((root/SOURCE_MANIFEST).read_text(encoding='utf-8'))
    if not isinstance(data,dict) or set(data)!={'version','files'} or type(data['version']) is not int or data['version']!=1 or not isinstance(data['files'],list):
        raise ValueError('invalid source disposition manifest schema')
    admitted=set();scopes=set();declared=set()
    for name in data['files']:
        if not isinstance(name,str) or not name: raise ValueError('invalid source disposition path')
        scope=name.endswith('/')
        path=name[:-1] if scope else name
        if not portable(path): raise ValueError('invalid source disposition path')
        relative=Path(path)
        if relative.is_absolute() or private(relative): raise ValueError('private or absolute source disposition path')
        if name.casefold() in declared: raise ValueError('duplicate source disposition path')
        declared.add(name.casefold());(scopes if scope else admitted).add(path)
    if SOURCE_MANIFEST.as_posix() not in admitted: raise ValueError('source disposition manifest must admit itself')
    if admitted & scopes: raise ValueError('source disposition file/directory collision')
    return admitted,scopes

def covered(name,admitted,scopes):
    return name in admitted or any(name.startswith(scope+'/') for scope in scopes)

def scope_path(name,scopes):
    return any(name==scope or name.startswith(scope+'/') or scope.startswith(name+'/') for scope in scopes)

def source_files(root,artifact=False):
    admitted,scopes=admitted_files(root)
    directories={parent.as_posix() for name in admitted for parent in Path(name).parents if parent!=Path('.')}
    if admitted & directories: raise ValueError('source disposition file/directory collision')
    found={}
    def walk(folder):
        for item in sorted(folder.iterdir()):
            relative=item.relative_to(root)
            if private(relative):
                if artifact: raise ValueError('forbidden distribution artifact: '+str(relative))
                continue
            if item.is_symlink(): raise ValueError('source link requires explicit disposition: '+str(relative))
            name=relative.as_posix()
            if not portable(name): raise ValueError('nonportable source path: '+name)
            if item.is_dir():
                if artifact and name not in directories and not scope_path(name,scopes): raise ValueError('unclassified source directory: '+name)
                walk(item)
            elif item.is_file():
                if not covered(name,admitted,scopes): raise ValueError('unclassified source file: '+name)
                found[name]=item
            else: raise ValueError('unreadable source entry: '+str(relative))
    walk(root)
    collisions=case_collisions(with_parents(found))
    if collisions: raise ValueError('case-insensitive path collision: '+' vs '.join(collisions[0][1]))
    missing=admitted-found.keys()
    if missing: raise ValueError('missing admitted source file: '+', '.join(sorted(missing)))
    absent=[scope for scope in sorted(scopes) if not (root/scope).is_dir()]
    if absent: raise ValueError('missing admitted source scope: '+', '.join(absent))
    yield from (found[name] for name in sorted(found))

def personal_candidates(root,files):
    pattern=re.compile(r'(?i)(?:/' + r'home/([a-z0-9_.@-]+)|(?:[a-z]:/|/mnt/[a-z]/|/[a-z]/)users/([a-z0-9_.@-]+))')
    neutral={'*','x','user','username','sample-user','example','...','fixture','test-user','sample person','sample'}
    findings=[]
    for file in files:
        value=file.read_text(encoding='utf-8',errors='replace').replace('\\\\','/').replace('\\','/')
        for number,line in enumerate(value.splitlines(),1):
            for match in pattern.finditer(line):
                name=next(g for g in match.groups() if g is not None).rstrip(')')
                if name.lower() not in neutral and not name.startswith(('$','{')):
                    findings.append(f'{file.relative_to(root)}:{number}: personal-path candidate')
    return findings

def scanner(folder,scratch):
    scratch.mkdir(parents=True,exist_ok=True)
    config=ROOT/'.gitleaks.toml'
    version=subprocess.run(['gitleaks','version'],capture_output=True,text=True,check=True).stdout.strip()
    if version.removeprefix('v')!='8.30.1': raise ValueError('Gitleaks 8.30.1 is required')
    def scan(target,report,expected):
        result=subprocess.run(['gitleaks','dir',str(target),'--config',str(config),'--redact=100','--no-banner','--ignore-gitleaks-allow','--gitleaks-ignore-path',os.devnull,'--exit-code','23','--report-format','json','--report-path',str(report)],capture_output=True)
        if result.returncode!=expected: raise ValueError('secret scanner failed or detected a finding; inspect source privately')
    control=scratch/'control';control.mkdir()
    (control/'control.txt').write_text('token = "'+'ghp_'+'a1b2c3d4e5a1b2c3d4e5a1b2c3d4e5abcdef'+'"\n')
    report=scratch/'control.json';scan(control,report,23)
    if not any(f['RuleID']=='github-pat' for f in json.loads(report.read_text())): raise ValueError('secret control produced no expected finding')
    missing=scratch/'missing-config.toml'
    failure=subprocess.run(['gitleaks','dir',str(control),'--config',str(missing),'--report-path',str(scratch/'error.json'),'--exit-code','23','--no-banner'],capture_output=True)
    if failure.returncode in (0,23) or (scratch/'error.json').exists(): raise ValueError('scanner error control did not fail distinctly')
    scan(folder,scratch/'source.json',0)

def export(root,destination):
    root=root.resolve(); destination=destination.resolve()
    if destination==root or root in destination.parents: raise ValueError('export must be outside its source')
    if destination.exists(): raise ValueError('export destination must be absent')
    files=list(source_files(root))
    destination.mkdir(parents=True)
    manifest={}
    for file in files:
        relative=file.relative_to(root);target=destination/relative
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy(file,target)
        if os.name=='posix' and bool(file.stat().st_mode & 0o111)!=bool(target.stat().st_mode & 0o111):
            raise ValueError('export destination did not preserve executable permissions: '+relative.as_posix())
        manifest[relative.as_posix()]=hashlib.sha256(target.read_bytes()).hexdigest()
    return manifest

def own_repository(root):
    try:
        (root/'.git').lstat()
    except FileNotFoundError:
        return False
    result=subprocess.run(['git','-C',str(root),'rev-parse','--show-toplevel'],capture_output=True,text=True)
    if result.returncode or Path(result.stdout.strip()).resolve()!=root.resolve():
        raise ValueError('cannot verify independent Git repository; metadata or Git configuration is invalid')
    return True


def check_index(root,scratch,required=False):
    entries=subprocess.check_output(['git','-C',str(root),'ls-files','--stage','-z']).decode().split('\0')
    indexed=[]
    for entry in filter(None,entries):
        metadata,name=entry.split('\t',1)
        mode,oid,stage=metadata.split()
        if mode not in ('100644','100755') or stage!='0': raise ValueError('unsupported indexed source entry: '+name)
        if private(Path(name)): raise ValueError('private file tracked: '+name)
        indexed.append(name)
    for name in indexed:
        if not portable(name): raise ValueError('nonportable indexed source path: '+name)
    collisions=case_collisions(with_parents(indexed))
    if collisions: raise ValueError('case-insensitive path collision: '+' vs '.join(collisions[0][1]))
    staged=scratch/'index';staged.mkdir()
    if indexed:
        if SOURCE_MANIFEST.as_posix() not in indexed: raise ValueError('unclassified indexed source file: missing staged manifest')
        manifest=staged/SOURCE_MANIFEST;manifest.parent.mkdir(parents=True)
        manifest.write_bytes(subprocess.check_output(['git','-C',str(root),'show',':'+SOURCE_MANIFEST.as_posix()]))
        admitted,scopes=admitted_files(staged)
        for name in indexed:
            if not covered(name,admitted,scopes): raise ValueError('unclassified indexed source file: '+name)
        for name in indexed:
            target=staged/name;target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(subprocess.check_output(['git','-C',str(root),'show',':'+name]))
        staged_files=list(source_files(staged,artifact=True))
        if personal_candidates(staged,staged_files): raise ValueError('personal path in staged source')
    elif required:
        raise ValueError('staged source has no reviewed manifest')
    scanner(staged,scratch/'staged-scan')


def check(root,artifact=False,staged_only=False):
    if artifact and staged_only: raise ValueError('artifact and staged checks are separate inputs')
    own_git=own_repository(root)
    if staged_only and not own_git: raise ValueError('staged checks require the source repository itself')
    files=[] if staged_only else list(source_files(root,artifact))
    findings=personal_candidates(root,files)
    if findings: raise ValueError('\n'.join(findings))
    scratch_root=ROOT/'tmp';scratch_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='public-check-',dir=scratch_root) as temporary:
        scratch=Path(temporary)
        if not staged_only:
            source=scratch/'source';source.mkdir()
            for file in files:
                target=source/file.relative_to(root);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(file,target)
            scanner(source,scratch/'working-scan')
        if own_git:
            check_index(root,scratch,required=staged_only)
            if not staged_only:
                refs=subprocess.check_output(['git','-C',str(root),'for-each-ref','--format=%(refname)']).strip()
                head=subprocess.run(['git','-C',str(root),'rev-parse','--verify','HEAD'],capture_output=True)
                if refs or head.returncode==0:
                    history=subprocess.run(['gitleaks','git',str(root),'--config',str(ROOT/'.gitleaks.toml'),'--log-opts=--all','--ignore-gitleaks-allow','--gitleaks-ignore-path',os.devnull,'--redact=100','--no-banner','--exit-code','23'],capture_output=True)
                    if history.returncode: raise ValueError('distributed Git history failed secret scanning')
    print(('Staged source' if staged_only else 'Source')+' privacy checks passed; manual identity, attribution and topology review is still required.')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='operation',required=True)
    p=sub.add_parser('export');p.add_argument('destination',type=Path);p.add_argument('--manifest',type=Path)
    p=sub.add_parser('check');p.add_argument('source',type=Path,nargs='?',default=ROOT);p.add_argument('--artifact',action='store_true');p.add_argument('--staged',action='store_true')
    args=parser.parse_args()
    try:
        if args.operation=='export':
            manifest=export(ROOT,args.destination)
            if args.manifest: args.manifest.write_text(json.dumps(manifest,indent=2)+'\n')
            print('Exported',len(manifest),'source files; private state excluded.')
        else: check(args.source.resolve(),args.artifact,args.staged)
    except (ValueError,OSError,subprocess.SubprocessError) as exc:
        print('REFUSED:',str(exc),file=sys.stderr);sys.exit(1)
