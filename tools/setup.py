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
from release import source_files

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('operation',choices=('init','check','test'))
args=parser.parse_args()
try:
    if args.operation=='init':
        target=ROOT/'config.local.json'
        if target.exists() or target.is_symlink():
            config.load();print('Local input already exists; preserved.')
        else:
            descriptor=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(descriptor,'wb') as stream: stream.write((ROOT/'config.local.example.json').read_bytes())
            print('Created private local input; optional connections remain disabled.')
    elif args.operation=='check':
        config.load()
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
