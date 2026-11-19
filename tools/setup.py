#!/usr/bin/env python3
"""Explicit local setup; no dependency acquisition or provider requests on init/check."""
import argparse
import ast
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'agents'))
import config
from release import source_files, own_repository

def install_hooks():
    if not own_repository(ROOT):
        print('Hook registration skipped: no independent Git repository.')
        return
    existing=subprocess.run(['git','-C',str(ROOT),'config','--get','core.hooksPath'],capture_output=True,text=True)
    if existing.returncode not in (0,1): raise ValueError('cannot inspect existing Git hook configuration')
    if existing.returncode==0 and existing.stdout.strip()!='.githooks':
        raise ValueError('foreign core.hooksPath preserved; integrate release hooks explicitly')
    if existing.returncode==1:
        hooks=Path(subprocess.check_output(['git','-C',str(ROOT),'rev-parse','--git-path','hooks'],text=True).strip())
        if not hooks.is_absolute(): hooks=ROOT/hooks
        if hooks.exists() and any(p.is_file() and not p.name.endswith('.sample') for p in hooks.iterdir()):
            raise ValueError('existing Git hooks preserved; integrate release hooks explicitly')
    for name in ('pre-commit','pre-push'):
        path=ROOT/'.githooks'/name
        if path.is_symlink() or not path.is_file(): raise ValueError('missing or linked release hook')
        if os.name=='posix' and not os.access(path,os.X_OK):
            raise ValueError('release hook is not executable; restore executable checkout permissions: '+name)
    subprocess.run(['git','-C',str(ROOT),'config','--local','core.hooksPath','.githooks'],check=True)
    print('Local pre-commit/pre-push release checks registered; Gitleaks 8.30.1 is required.')


parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('operation',choices=('init','hooks','check','test'))
args=parser.parse_args()
try:
    if args.operation=='init':
        target=config.local_path()
        if target.exists() or target.is_symlink():
            config.load();print('Local input already exists; preserved.')
        else:
            example=(ROOT/'config.local.example.jsonc').read_bytes()
            config.parse(example,commented=True)
            descriptor=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(descriptor,'wb') as stream: stream.write(example)
            print('Created private local input; optional connections remain disabled.')
        install_hooks()
    elif args.operation=='hooks':
        install_hooks()
    elif args.operation=='check':
        _,local=config.load()
        print('Local input: '+config.local_path().name+'; sections: '+(', '.join(sorted(local)) or 'none')+' (values hidden).')
        subprocess.run([sys.executable,str(ROOT/'agents/providers/claude/settings.py'),'validate'],check=True)
        pi=config.pi_input()
        if pi['configured']:
            subprocess.run(['node',str(ROOT/'agents/providers/pi/runtime/configure.js'),'schema','--local'],input=json.dumps(pi),text=True,check=True)
        for file in source_files(ROOT):
            if file.suffix=='.py': ast.parse(file.read_text(encoding='utf-8'))
            if file.suffix=='.sh': subprocess.run(['bash','-n',str(file)],check=True)
        print('Source/local configuration checks passed; no native settings changed.')
    else:
        scratch=ROOT/'tmp';scratch.mkdir(exist_ok=True)
        env=dict(os.environ,TMPDIR=str(scratch),PYTHONDONTWRITEBYTECODE='1')
        subprocess.run(['bash',str(ROOT/'agents/tests/run-tests.sh')],cwd=ROOT,env=env,check=True)
except (OSError,ValueError,config.ConfigError,subprocess.SubprocessError) as exc:
    print('Setup refused:',str(exc),file=sys.stderr);sys.exit(1)
