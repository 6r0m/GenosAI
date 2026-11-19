"""Local Git release gates use independent reviewed snapshots without changing the index."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
BASH=shutil.which('bash') or 'bash'
spec=importlib.util.spec_from_file_location('hook_release',ROOT/'tools/release.py')
release=importlib.util.module_from_spec(spec);spec.loader.exec_module(release)


class ReleaseHooks(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='release-hooks-')
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.root=self.base/'source';self.root.mkdir()
        for source in release.source_files(ROOT):
            target=self.root/source.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy(source,target)
        self.env=dict(os.environ,HOME=str(self.base/'home'),PYTHONDONTWRITEBYTECODE='1')
        for key in ('GIT_DIR','GIT_WORK_TREE','GIT_INDEX_FILE'):self.env.pop(key,None)
        self.git('init','-q')

    def git(self,*args):
        return subprocess.check_output(['git','-C',str(self.root),*args],env=self.env,stderr=subprocess.PIPE)

    def setup(self,operation):
        return subprocess.run([sys.executable,'tools/setup.py',operation],cwd=self.root,env=self.env,capture_output=True,text=True)

    def hook(self,name):
        before=self.git('ls-files','--stage','-z')
        result=subprocess.run([BASH,(self.root/'.githooks'/name).as_posix()],cwd=self.root,env=self.env,capture_output=True,text=True)
        self.assertEqual(self.git('ls-files','--stage','-z'),before)
        return result

    @unittest.skipUnless(os.name=='posix','Unix executable permissions')
    def test_non_executable_hook_refuses_without_source_or_config_changes(self):
        hooks=[self.root/'.githooks'/name for name in ('pre-commit','pre-push')]
        hooks[0].chmod(0o644)
        before=[(p.read_bytes(),p.stat().st_mode) for p in hooks]
        configuration=(self.root/'.git/config').read_bytes()
        index=self.git('ls-files','--stage','-z')
        result=self.setup('hooks')
        self.assertNotEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('not executable',result.stderr)
        self.assertEqual([(p.read_bytes(),p.stat().st_mode) for p in hooks],before)
        self.assertEqual((self.root/'.git/config').read_bytes(),configuration)
        self.assertEqual(self.git('ls-files','--stage','-z'),index)

    @unittest.skipUnless(os.name=='posix' and shutil.which('make'),'Unix checkout and Make')
    def test_init_and_hooks_preserve_a_clean_executable_checkout(self):
        self.git('config','core.filemode','true')
        # Local permissions can be narrower than Git's single executable bit.
        (self.root/'.githooks/pre-commit').chmod(0o750)
        self.git('add','.')
        self.git('-c','core.hooksPath='+os.devnull,'-c','user.name=Fixture',
                 '-c','user.email=fixture@example.invalid','-c','commit.gpgsign=false',
                 'commit','-qm','Synthetic clean-checkout fixture')
        self.assertEqual(self.git('status','--porcelain=v1','--untracked-files=all'),b'')
        hooks=[self.root/'.githooks'/name for name in ('pre-commit','pre-push')]
        before=[(p.read_bytes(),p.stat().st_mode) for p in hooks]
        index=self.git('ls-files','--stage','-z')
        for operation in ('hooks','init','init','hooks'):
            result=subprocess.run(['make',operation,'PYTHON='+sys.executable],cwd=self.root,
                                  env=self.env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual(self.git('status','--porcelain=v1','--untracked-files=all'),b'')
            self.assertEqual([(p.read_bytes(),p.stat().st_mode) for p in hooks],before)
            self.assertEqual(self.git('ls-files','--stage','-z'),index)

    def test_registration_is_local_repeatable_and_preserves_local_json(self):
        local=self.root/'config.local.json';raw=b'{"browser":{"cdp_url":null}}\n';local.write_bytes(raw)
        for _ in range(2):
            result=self.setup('init');self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(self.git('config','--local','--get','core.hooksPath').strip(),b'.githooks')
        self.assertEqual(local.read_bytes(),raw)
        self.assertFalse(local.with_suffix('.jsonc').exists())
        self.assertEqual(self.git('ls-files'),b'')

    def test_foreign_hook_configuration_and_active_hooks_are_preserved(self):
        foreign=self.base/'foreign-hooks';foreign.mkdir()
        self.git('config','--local','core.hooksPath',str(foreign))
        result=self.setup('hooks');self.assertNotEqual(result.returncode,0)
        self.assertIn('foreign core.hooksPath',result.stderr)
        self.assertEqual(self.git('config','--local','--get','core.hooksPath').decode().strip(),str(foreign))
        self.git('config','--local','--unset','core.hooksPath')
        hook=self.root/'.git/hooks/pre-commit';hook.write_text('#!/bin/sh\nexit 0\n');raw=hook.read_bytes()
        result=self.setup('hooks');self.assertNotEqual(result.returncode,0)
        self.assertIn('existing Git hooks',result.stderr);self.assertEqual(hook.read_bytes(),raw)

    def test_broken_git_metadata_refuses_registration_and_push_check(self):
        metadata=self.root/'.git/config';metadata.write_text('[broken configuration')
        before=metadata.read_bytes()
        for result in (self.setup('hooks'), subprocess.run([BASH,(self.root/'.githooks/pre-push').as_posix()],cwd=self.root,env=self.env,capture_output=True,text=True)):
            self.assertNotEqual(result.returncode,0)
        self.assertEqual(metadata.read_bytes(),before)
        with self.assertRaisesRegex(ValueError,'cannot verify independent Git'):
            release.check(self.root)

    @unittest.skipUnless(os.name=='posix','shell preflight test')
    def test_unconfigured_pi_refuses_before_node_lookup_or_home_writes(self):
        home=self.base/'home';home.mkdir()
        script=r"""
source "$1"
AI_ROOT="$2"
operation=install
PI_NODE_REL=missing-node
command() { printf 'unexpected Node lookup\n' >&2; return 1; }
pi_preflight
"""
        result=subprocess.run([BASH,'-c',script,'fixture',str(self.root/'agents/providers/pi/lifecycle.sh'),str(self.root/'agents')],
                              env=self.env,capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('unconfigured',result.stderr)
        self.assertNotIn('Node lookup',result.stderr)
        self.assertEqual(list(home.iterdir()),[])

    @unittest.skipUnless(shutil.which('gitleaks'),'requires pinned Gitleaks')
    def test_staged_snapshot_uses_its_own_manifest_and_rejects_staged_secret(self):
        self.git('add','.')
        # Working-only additions do not change what pre-commit judges.
        (self.root/'unreviewed.md').write_text('working-only synthetic note')
        result=self.hook('pre-commit');self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        result=self.hook('pre-push');self.assertNotEqual(result.returncode,0)
        self.assertIn('unclassified',result.stderr)
        file=self.root/'README.md';original=file.read_bytes()
        file.write_text('token = "'+'ghp_'+'a1b2c3d4e5a1b2c3d4e5a1b2c3d4e5abcdef'+'"\n')
        self.git('add','README.md');file.write_bytes(original)
        result=self.hook('pre-commit');self.assertNotEqual(result.returncode,0)
        self.assertNotIn('a1b2c3d4',result.stdout+result.stderr)

    def test_force_added_jsonc_refuses_without_index_mutation(self):
        self.git('add','.')
        private=self.root/'config.local.jsonc';private.write_text('{/* synthetic private */}')
        self.git('add','-f','config.local.jsonc')
        result=self.hook('pre-commit');self.assertNotEqual(result.returncode,0)
        self.assertIn('private file tracked',result.stderr)

    @unittest.skipUnless(os.name=='posix','POSIX isolated interpreter lookup')
    def test_strict_resolver_refuses_when_python_is_absent(self):
        binary=self.base/'bin';binary.mkdir();(binary/'dirname').symlink_to(shutil.which('dirname'))
        script=self.root/'agents/permissions/run-guard.sh'
        result=subprocess.run([shutil.which('bash'),str(script),'--strict','../../../tools/release.py','check','--staged'],
                              cwd=self.root,env=dict(self.env,PATH=str(binary)),capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0);self.assertEqual(result.stdout,'')
        self.assertIn('no working Python',result.stderr)

    @unittest.skipUnless(os.name=='posix','POSIX isolated scanner lookup')
    def test_hook_refuses_when_scanner_is_missing(self):
        self.git('add','.')
        binary=self.base/'bin';binary.mkdir()
        for name,source in (('dirname',shutil.which('dirname')),('git',shutil.which('git')),('bash',shutil.which('bash')),('python3',sys.executable)):
            (binary/name).symlink_to(source)
        self.env['PATH']=str(binary)
        result=self.hook('pre-commit');self.assertNotEqual(result.returncode,0)
        self.assertIn('gitleaks',result.stderr)


if __name__=='__main__':unittest.main()
